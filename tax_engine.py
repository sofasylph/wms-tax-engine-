# tax_engine.py

import os
import json
import logging
from functools import lru_cache
from typing import Optional
from flask import Flask, request, jsonify

# —————————————————————————————————————————————————————
# Logging Configuration
logger = logging.getLogger("TaxEngine")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("tax_engine.log")
formatter = logging.Formatter('%(asctime)s %(levelname)s:%(name)s:%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# —————————————————————————————————————————————————————
# Utilities

def round_amount(amount: float, ndigits: int = 2) -> float:
    """Round to currency precision by default."""
    return round(amount, ndigits)

def convert_to_inr(amount: float, currency: str) -> float:
    """
    Stub for currency conversion. Integrate with real FX rates.
    """
    rates = {"USD": 82.5, "EUR": 90.0}  
    rate = rates.get(currency.upper())
    if rate is None:
        logger.warning(f"No FX rate for {currency}, assuming 1:1")
        return amount
    return amount * rate

# —————————————————————————————————————————————————————
# Compensation Cess Engine

class CompensationCessEngine:
    """
    Calculates Compensation Cess by HSN code using dynamic rules.
    """
    def __init__(self):
        # Load rules from JSON
        rules_path = os.path.join(os.path.dirname(__file__), "cess_rules.json")
        try:
            with open(rules_path) as f:
                self.rules = json.load(f)
            logger.info(f"Loaded {len(self.rules)} cess rules")
        except Exception as e:
            logger.exception(f"Failed to load cess rules: {e}")
            self.rules = {}

    @lru_cache(maxsize=1024)
    def _get_rule(self, hsn: str):
        return self.rules.get(hsn)

    def calculate_cess(self,
                       hsn: str,
                       transaction_value: Optional[float] = None,
                       quantity: Optional[float] = None,
                       weight_tonnes: Optional[float] = None) -> float:
        try:
            rule = self._get_rule(hsn)
            if not rule:
                logger.warning(f"Cess rule not found for HSN: {hsn}")
                return 0.0

            rtype = rule.get('type')
            if rtype == 'ad_valorem':
                return transaction_value * (rule['rate_percent'] / 100)
            if rtype == 'fixed_per_unit':
                return (quantity / rule['unit_count']) * rule['fixed_rate']
            if rtype == 'per_weight':
                return weight_tonnes * rule['rate_per_tonne']
            if rtype == 'combined':
                ad = transaction_value * (rule['rate_percent'] / 100)
                pu = (quantity / rule['unit_count']) * rule['fixed_rate']
                return ad + pu
            if rtype == 'higher_of':
                best = 0.0
                for opt in rule['options']:
                    # calculate each option individually
                    sub_amt = CompensationCessEngine().calculate_cess(
                        hsn,
                        transaction_value=transaction_value,
                        quantity=quantity,
                        weight_tonnes=weight_tonnes
                    )
                    best = max(best, sub_amt)
                return best

            logger.error(f"Unknown rule type '{rtype}' for HSN {hsn}")
            return 0.0

        except Exception as e:
            logger.exception(f"Error calculating cess for HSN {hsn}: {e}")
            return 0.0

# —————————————————————————————————————————————————————
# GST Engine

class GSTEngine:
    """
    Calculates CGST/SGST or IGST based on transaction context.
    """
    def calculate_gst(self,
                      transaction_value: float,
                      gst_rate: float,
                      interstate: bool = False):
        try:
            if interstate:
                igst = transaction_value * (gst_rate / 100)
                return 0.0, 0.0, igst
            half = gst_rate / 2
            cg = transaction_value * (half / 100)
            return cg, cg, 0.0
        except Exception as e:
            logger.exception(f"Error calculating GST: {e}")
            return 0.0, 0.0, 0.0

# —————————————————————————————————————————————————————
# Main Entry Point

def calculate_taxes_for_line(form_data: dict) -> dict:
    """
    form_data must include:
      - hsn: str
      - base_price: float (assessable value)
      - qty_uom: float
      - weight_grams: Optional[float]
      - gst_rate: float
      - interstate: bool
      - currency: str (e.g. 'INR','USD')
      - category: str (e.g. 'Default' or 'Custom')
    """
    # Extract & preprocess
    hsn             = form_data['hsn']
    category        = form_data.get('category', 'Default')
    assessable_value= float(form_data['base_price'])
    quantity        = float(form_data.get('qty_uom', 0))
    weight_grams    = form_data.get('weight_grams')
    gst_rate        = float(form_data.get('gst_rate', 0))
    interstate      = bool(form_data.get('interstate', False))
    currency        = form_data.get('currency', 'INR')

    # Currency conversion
    if currency != 'INR':
        assessable_value = convert_to_inr(assessable_value, currency)

    # Unit conversion: grams → tonnes
    weight_tonnes = None
    if weight_grams is not None:
        weight_tonnes = float(weight_grams) / 1_000_000

    # Compute GST
    cgst, sgst, igst = GSTEngine().calculate_gst(
        assessable_value, gst_rate, interstate
    )
    cgst, sgst, igst = map(round_amount, (cgst, sgst, igst))

    # Compute Compensation Cess
    cess = 0.0
    if category != 'Custom':
        cess = CompensationCessEngine().calculate_cess(
            hsn,
            transaction_value=assessable_value,
            quantity=quantity,
            weight_tonnes=weight_tonnes
        )
        cess = round_amount(cess)
    else:
        logger.info(f"Custom category for HSN {hsn}: skipping auto-cess")

    total_tax = round_amount(cgst + sgst + igst + cess)

    result = {
        'HSN': hsn,
        'Category': category,
        'AssessableValue': assessable_value,
        'Quantity': quantity,
        'WeightTonnes': weight_tonnes,
        'CGST': cgst,
        'SGST': sgst,
        'IGST': igst,
        'CompensationCess': cess,
        'TotalTax': total_tax
    }
    logger.info(f"Tax calc: {result}")
    return result

# —————————————————————————————————————————————————————
# Flask API Endpoint

app = Flask(__name__)

@app.route("/api/taxes", methods=["GET", "POST"])
def api_taxes():
    try:
        data = request.json if request.method == "POST" else request.args.to_dict()
        result = calculate_taxes_for_line(data)
        return jsonify(result)
    except KeyError as ke:
        logger.error(f"Missing parameter: {ke}")
        return jsonify({"error": f"Missing parameter: {ke}"}), 400
    except ValueError as ve:
        logger.error(f"Invalid data: {ve}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Tax API internal error")
        return jsonify({"error": "Internal server error"}), 500

# —————————————————————————————————————————————————————
if __name__ == "__main__":
    # For local testing only; in production run under WSGI
    app.run(host="0.0.0.0", port=8000, debug=False)
