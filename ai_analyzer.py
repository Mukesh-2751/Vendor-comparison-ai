import re


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(text):
    """Clean PDF extracted text."""

    if not text:
        return ""

    text = text.replace("\xa0", " ")

    # Normalize spaces but keep lines
    lines = []

    for line in text.splitlines():

        line = re.sub(r"\s+", " ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def find_value(text, patterns):

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            value = re.sub(
                r"\s+",
                " ",
                value
            )

            return value

    return None


def number_from_text(value):

    if value is None:
        return None

    match = re.search(
        r"[\d,]+(?:\.\d+)?",
        str(value)
    )

    if not match:
        return None

    try:

        return float(
            match.group()
            .replace(",", "")
        )

    except Exception:

        return None


# ============================================================
# VENDOR EXTRACTION
# ============================================================

def extract_vendor_data(text):

    text = clean_text(text)

    # --------------------------------------------------------
    # VENDOR
    # --------------------------------------------------------

    vendor = find_value(
        text,
        [
            r"(?:vendor|supplier|company|seller|vendor name|supplier name)\s*[:\-]\s*(.+)",
            r"(?:quoted by|quotation from)\s*[:\-]\s*(.+)"
        ]
    )

    # Try finding a company-like line if label was not found
    if not vendor:

        for line in text.splitlines():

            if re.search(
                r"\b(pvt\.?\s*ltd|private limited|ltd\.?|inc\.?|llp|solutions|technologies|enterprises|industries)\b",
                line,
                re.IGNORECASE
            ):

                if len(line) < 120:

                    vendor = line.strip()

                    break

    # --------------------------------------------------------
    # QUOTATION NUMBER
    # --------------------------------------------------------

    quotation_number = find_value(
        text,
        [
            r"(?:quotation\s*(?:no|number|#)|quote\s*(?:no|number|#)|quotation id)\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)",
        ]
    )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    quotation_date = find_value(
        text,
        [
            r"(?:quotation date|quote date|date)\s*[:\-]\s*([^\n]+)",
        ]
    )

    # --------------------------------------------------------
    # VALIDITY
    # --------------------------------------------------------

    validity = find_value(
        text,
        [
            r"(?:validity|valid for|quotation valid)\s*[:\-]\s*([^\n]+)",
        ]
    )

    # --------------------------------------------------------
    # CURRENCY
    # --------------------------------------------------------

    currency = None

    if "₹" in text or re.search(
        r"\bINR\b|\bRs\.?\b|\bRupees\b",
        text,
        re.IGNORECASE
    ):
        currency = "INR"

    elif "$" in text or re.search(
        r"\bUSD\b",
        text,
        re.IGNORECASE
    ):
        currency = "USD"

    elif "€" in text or re.search(
        r"\bEUR\b",
        text,
        re.IGNORECASE
    ):
        currency = "EUR"

    elif "£" in text or re.search(
        r"\bGBP\b",
        text,
        re.IGNORECASE
    ):
        currency = "GBP"

    # --------------------------------------------------------
    # TOTAL PRICE
    # --------------------------------------------------------

    total_price = find_value(
        text,
        [
            r"(?:grand total|total amount|net total|total price|amount payable|quotation total)\s*[:\-]?\s*(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d+)?)"
        ]
    )

    total_price = number_from_text(
        total_price
    )

    # --------------------------------------------------------
    # SUBTOTAL
    # --------------------------------------------------------

    subtotal = find_value(
        text,
        [
            r"(?:subtotal|sub total)\s*[:\-]?\s*(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d+)?)"
        ]
    )

    subtotal = number_from_text(
        subtotal
    )

    # --------------------------------------------------------
    # TAX
    # --------------------------------------------------------

    tax = find_value(
        text,
        [
            r"(?:tax|gst|vat|sales tax)\s*[:\-]?\s*(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d+)?)"
        ]
    )

    tax = number_from_text(
        tax
    )

    # --------------------------------------------------------
    # SHIPPING
    # --------------------------------------------------------

    shipping = find_value(
        text,
        [
            r"(?:shipping|delivery charges|freight|transportation)\s*(?:charges?)?\s*[:\-]?\s*(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d+)?)"
        ]
    )

    shipping = number_from_text(
        shipping
    )

    # --------------------------------------------------------
    # DISCOUNT
    # --------------------------------------------------------

    discount = find_value(
        text,
        [
            r"(?:discount)\s*[:\-]?\s*(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d+)?)"
        ]
    )

    discount = number_from_text(
        discount
    )

    # --------------------------------------------------------
    # DELIVERY
    # --------------------------------------------------------

    delivery = find_value(
        text,
        [
            r"(?:delivery|delivery time|lead time|shipping time)\s*[:\-]\s*([^\n]+)",
            r"(?:delivery|lead time)\s*[:\-]?\s*(\d+\s*(?:days?|weeks?))"
        ]
    )

    # --------------------------------------------------------
    # WARRANTY
    # --------------------------------------------------------

    warranty = find_value(
        text,
        [
            r"(?:warranty|guarantee)\s*[:\-]\s*([^\n]+)"
        ]
    )

    # --------------------------------------------------------
    # PAYMENT
    # --------------------------------------------------------

    payment_terms = find_value(
        text,
        [
            r"(?:payment terms?|payment conditions?)\s*[:\-]\s*([^\n]+)",
            r"(?:terms of payment)\s*[:\-]\s*([^\n]+)"
        ]
    )

    # --------------------------------------------------------
    # ITEMS
    # --------------------------------------------------------

    items = []

    lines = text.splitlines()

    for i, line in enumerate(lines):

        # Detect lines containing quantity and price
        if re.search(
            r"\bqty\b|\bquantity\b",
            line,
            re.IGNORECASE
        ):

            continue

        price_matches = re.findall(
            r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)?\s*[\d,]+(?:\.\d+)?",
            line
        )

        if price_matches:

            # Avoid treating summary lines as products
            if re.search(
                r"total|subtotal|tax|gst|shipping|discount|amount payable",
                line,
                re.IGNORECASE
            ):
                continue

            quantity_match = re.search(
                r"\b(\d+)\s*(?:units?|pcs?|pieces?|nos?)?\b",
                line,
                re.IGNORECASE
            )

            if quantity_match:

                quantity = int(
                    quantity_match.group(1)
                )

                numbers = []

                for p in price_matches:

                    n = number_from_text(p)

                    if n is not None:
                        numbers.append(n)

                if numbers:

                    items.append(
                        {
                            "product_or_service": line,
                            "description": line,
                            "quantity": quantity,
                            "unit": "unit",
                            "unit_price": numbers[-1],
                            "total_price": None,
                            "specifications": []
                        }
                    )

    # --------------------------------------------------------
    # FALLBACK ITEM
    # --------------------------------------------------------

    if not items:

        items = []

    # --------------------------------------------------------
    # ADDITIONAL CHARGES
    # --------------------------------------------------------

    additional_charges = []

    if shipping is not None:

        additional_charges.append(
            f"Shipping/Freight: {shipping}"
        )

    # --------------------------------------------------------
    # NOTES
    # --------------------------------------------------------

    notes = []

    for line in lines:

        if re.search(
            r"note|remark|special condition",
            line,
            re.IGNORECASE
        ):

            notes.append(line)

    # --------------------------------------------------------
    # RETURN STRUCTURED DATA
    # --------------------------------------------------------

    return {
        "vendor": vendor,
        "quotation_number": quotation_number,
        "quotation_date": quotation_date,
        "validity": validity,
        "currency": currency,

        "items": items,

        "subtotal": subtotal,
        "tax": tax,
        "shipping": shipping,
        "discount": discount,
        "total_price": total_price,

        "delivery": delivery,
        "warranty": warranty,
        "payment_terms": payment_terms,

        "additional_charges": additional_charges,
        "notes": notes
    }


# ============================================================
# RFQ COMPLIANCE ANALYSIS
# ============================================================

def analyze_compliance(
    rfq_text,
    vendor_data
):

    rfq = clean_text(
        rfq_text
    ).lower()

    results = []

    # --------------------------------------------------------
    # RAM
    # --------------------------------------------------------

    rfq_ram = re.search(
        r"ram\s*[:\-]?\s*(\d+)\s*gb",
        rfq,
        re.IGNORECASE
    )

    vendor_text = str(
        vendor_data
    ).lower()

    vendor_ram = re.search(
        r"ram\s*[:\-]?\s*(\d+)\s*gb",
        vendor_text,
        re.IGNORECASE
    )

    if rfq_ram and vendor_ram:

        required = int(
            rfq_ram.group(1)
        )

        offered = int(
            vendor_ram.group(1)
        )

        if offered >= required:

            results.append(
                {
                    "requirement": f"RAM ≥ {required} GB",
                    "offered": f"{offered} GB",
                    "status": "COMPLIANT"
                }
            )

        else:

            results.append(
                {
                    "requirement": f"RAM ≥ {required} GB",
                    "offered": f"{offered} GB",
                    "status": "NON-COMPLIANT"
                }
            )

    # --------------------------------------------------------
    # STORAGE
    # --------------------------------------------------------

    rfq_storage = re.search(
        r"storage\s*[:\-]?\s*(\d+)\s*gb",
        rfq,
        re.IGNORECASE
    )

    vendor_storage = re.search(
        r"storage\s*[:\-]?\s*(\d+)\s*gb",
        vendor_text,
        re.IGNORECASE
    )

    if rfq_storage and vendor_storage:

        required = int(
            rfq_storage.group(1)
        )

        offered = int(
            vendor_storage.group(1)
        )

        results.append(
            {
                "requirement": f"Storage ≥ {required} GB",
                "offered": f"{offered} GB",
                "status": (
                    "COMPLIANT"
                    if offered >= required
                    else "NON-COMPLIANT"
                )
            }
        )

    # --------------------------------------------------------
    # DELIVERY
    # --------------------------------------------------------

    rfq_delivery = re.search(
        r"(?:delivery|lead time).*?(\d+)\s*days?",
        rfq,
        re.IGNORECASE
    )

    vendor_delivery = re.search(
        r"(\d+)\s*(?:days?|weeks?)",
        str(
            vendor_data.get(
                "delivery"
            )
            or ""
        ),
        re.IGNORECASE
    )

    if rfq_delivery and vendor_delivery:

        required = int(
            rfq_delivery.group(1)
        )

        offered = int(
            vendor_delivery.group(1)
        )

        results.append(
            {
                "requirement": f"Delivery ≤ {required} days",
                "offered": f"{offered} days",
                "status": (
                    "COMPLIANT"
                    if offered <= required
                    else "NON-COMPLIANT"
                )
            }
        )

    # --------------------------------------------------------
    # WARRANTY
    # --------------------------------------------------------

    rfq_warranty = re.search(
        r"(?:warranty|guarantee).*?(\d+)\s*years?",
        rfq,
        re.IGNORECASE
    )

    vendor_warranty = re.search(
        r"(\d+)\s*years?",
        str(
            vendor_data.get(
                "warranty"
            )
            or ""
        ),
        re.IGNORECASE
    )

    if rfq_warranty and vendor_warranty:

        required = int(
            rfq_warranty.group(1)
        )

        offered = int(
            vendor_warranty.group(1)
        )

        results.append(
            {
                "requirement": f"Warranty ≥ {required} years",
                "offered": f"{offered} years",
                "status": (
                    "COMPLIANT"
                    if offered >= required
                    else "NON-COMPLIANT"
                )
            }
        )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    if not results:

        return {
            "status": "REVIEW",
            "checks": [],
            "message": (
                "No directly comparable "
                "requirements were detected."
            )
        }

    failed = sum(
        1
        for r in results
        if r["status"] == "NON-COMPLIANT"
    )

    if failed == 0:

        status = "COMPLIANT"

    else:

        status = "NON-COMPLIANT"

    return {
        "status": status,
        "checks": results,
        "message": (
            "Vendor satisfies detected RFQ requirements."
            if status == "COMPLIANT"
            else
            f"{failed} requirement(s) failed."
        )
    }
    
def analyze_compliance(rfq_text, vendor_data):

    rfq = rfq_text.lower()
    vendor_text = str(vendor_data).lower()

    results = []

    # RAM
    rfq_ram = re.search(
        r"ram\s*[:\-]?\s*(\d+)\s*gb",
        rfq,
        re.IGNORECASE
    )

    vendor_ram = re.search(
        r"ram\s*[:\-]?\s*(\d+)\s*gb",
        vendor_text,
        re.IGNORECASE
    )

    if rfq_ram and vendor_ram:

        required = int(rfq_ram.group(1))
        offered = int(vendor_ram.group(1))

        results.append({
            "requirement": f"RAM >= {required} GB",
            "offered": f"{offered} GB",
            "status": (
                "COMPLIANT"
                if offered >= required
                else "NON-COMPLIANT"
            )
        })

    # Storage
    rfq_storage = re.search(
        r"storage\s*[:\-]?\s*(\d+)\s*gb",
        rfq,
        re.IGNORECASE
    )

    vendor_storage = re.search(
        r"storage\s*[:\-]?\s*(\d+)\s*gb",
        vendor_text,
        re.IGNORECASE
    )

    if rfq_storage and vendor_storage:

        required = int(rfq_storage.group(1))
        offered = int(vendor_storage.group(1))

        results.append({
            "requirement": f"Storage >= {required} GB",
            "offered": f"{offered} GB",
            "status": (
                "COMPLIANT"
                if offered >= required
                else "NON-COMPLIANT"
            )
        })

    # Delivery
    rfq_delivery = re.search(
        r"(?:delivery|lead time).*?(\d+)\s*days?",
        rfq,
        re.IGNORECASE
    )

    vendor_delivery = re.search(
        r"(\d+)\s*days?",
        str(vendor_data.get("delivery") or ""),
        re.IGNORECASE
    )

    if rfq_delivery and vendor_delivery:

        required = int(rfq_delivery.group(1))
        offered = int(vendor_delivery.group(1))

        results.append({
            "requirement": f"Delivery <= {required} days",
            "offered": f"{offered} days",
            "status": (
                "COMPLIANT"
                if offered <= required
                else "NON-COMPLIANT"
            )
        })

    # Warranty
    rfq_warranty = re.search(
        r"(?:warranty|guarantee).*?(\d+)\s*years?",
        rfq,
        re.IGNORECASE
    )

    vendor_warranty = re.search(
        r"(\d+)\s*years?",
        str(vendor_data.get("warranty") or ""),
        re.IGNORECASE
    )

    if rfq_warranty and vendor_warranty:

        required = int(rfq_warranty.group(1))
        offered = int(vendor_warranty.group(1))

        results.append({
            "requirement": f"Warranty >= {required} years",
            "offered": f"{offered} years",
            "status": (
                "COMPLIANT"
                if offered >= required
                else "NON-COMPLIANT"
            )
        })

    # Final result
    failed = sum(
        1 for x in results
        if x["status"] == "NON-COMPLIANT"
    )

    if not results:
        status = "REVIEW"
        message = "No directly comparable requirements detected."

    elif failed == 0:
        status = "COMPLIANT"
        message = "Vendor satisfies detected RFQ requirements."

    else:
        status = "NON-COMPLIANT"
        message = f"{failed} requirement(s) failed."

    return {
        "status": status,
        "checks": results,
        "message": message
    }