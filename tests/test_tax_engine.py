import pytest
from tax_engine import CompensationCessEngine, GSTEngine, calculate_taxes_for_line

# --- Compensation Cess Engine Tests ---

@pytest.mark.parametrize("hsn,val,qty,wt,expected", [
    ("21069020", 1000, 0, None, 600.0),   # 60% of 1000
    ("22021010",  500,  0, None,  60.0),   # 12% of  500
    ("2701",        0,  0,   2.5, 1000.0),  # 2.5 tonnes × 400
    ("24022010", 10000, 1000, None, 10000*0.05 + 1591.0),
    ("24021010", 1000,    0, None, max(1000*0.21, 4170.0/1000*1000)),
    ("99999999",  1000,    1, None, 0.0)    # missing rule → 0
])
def test_cess_engine(hsn, val, qty, wt, expected):
    engine = CompensationCessEngine()
    amt = engine.calculate_cess(hsn, transaction_value=val, quantity=qty, weight_tonnes=wt)
    assert pytest.approx(amt, rel=1e-3) == expected

# --- GST Engine Tests ---

@pytest.mark.parametrize("val,rate,inter,exp", [
    (1000, 18, False, (90.0, 90.0, 0.0)), # CGST=SGST=9%*1000
    ( 500, 18,  True, ( 0.0,  0.0, 90.0))
])
def test_gst_engine(val, rate, inter, exp):
    eg = GSTEngine()
    assert eg.calculate_gst(val, rate, inter) == exp

# --- Full Integration Tests ---

def test_calculate_line_default():
    data = {
        "hsn": "21069020",
        "base_price": 2000,
        "qty_uom": 0,
        "weight_grams": None,
        "gst_rate": 18,
        "interstate": False,
        "currency": "INR",
        "category": "Default"
    }
    result = calculate_taxes_for_line(data)
    # CGST 9% of 2000 = 180, SGST=180, Cess=60% of 2000=1200
    assert result["CGST"] == 180.0
    assert result["SGST"] == 180.0
    assert result["CompensationCess"] == 1200.0
    assert result["TotalTax"] == pytest.approx(180+180+1200)

def test_calculate_line_custom():
    data = {
        "hsn": "21069020",
        "base_price": 2000,
        "qty_uom": 0,
        "weight_grams": None,
        "gst_rate": 18,
        "interstate": False,
        "currency": "INR",
        "category": "Custom"  # skip auto-cess
    }
    result = calculate_taxes_for_line(data)
    assert result["CompensationCess"] == 0.0
    assert result["TotalTax"] == pytest.approx(180+180)

