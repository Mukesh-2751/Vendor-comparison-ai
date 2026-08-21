import streamlit as st
import fitz
import pandas as pd
import plotly.express as px
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from utils.ai_analyzer import (extract_vendor_data, analyze_compliance)

vendors = []

st.set_page_config(
    page_title="ProcureAI",
    page_icon="🏢",
    layout="wide"
)

def extract_pdf_text(uploaded_file):
    pdf_bytes = uploaded_file.read()
    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )
    text = ""
    for page in document:
        text += page.get_text()
        text += "\n"
    document.close()
    return text

def to_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        cleaned = str(value)
        cleaned = cleaned.replace(
            ",",
            ""
        )
        cleaned = cleaned.replace(
            "₹",
            ""
        )
        cleaned = cleaned.replace(
            "$",
            ""
        )
        cleaned = cleaned.replace(
            "€",
            ""
        )
        return float(cleaned)
    except Exception:
        return None


def get_total_price(data):

    total = to_number(
        data.get("total_price")
    )

    if total is not None:
        return total

    subtotal = to_number(
        data.get("subtotal")
    )

    tax = to_number(
        data.get("tax")
    )

    shipping = to_number(
        data.get("shipping")
    )

    if subtotal is not None:

        total = subtotal

        if tax is not None:
            total += tax

        if shipping is not None:
            total += shipping

        return total

    # Try calculating from items
    item_total = 0

    found_item_price = False

    for item in data.get(
        "items",
        []
    ):

        quantity = to_number(
            item.get("quantity")
        )

        unit_price = to_number(
            item.get("unit_price")
        )

        item_price = to_number(
            item.get("total_price")
        )

        if item_price is not None:

            item_total += item_price

            found_item_price = True

        elif (
            quantity is not None
            and unit_price is not None
        ):

            item_total += (
                quantity * unit_price
            )

            found_item_price = True

    if found_item_price:

        return item_total

    return None


# ============================================================
# EXTRACT DELIVERY DAYS
# ============================================================

def extract_delivery_days(value):

    if value is None:
        return None

    import re

    match = re.search(
        r"(\d+)",
        str(value)
    )

    if match:

        return int(
            match.group(1)
        )

    return None


# ============================================================
# WARRANTY YEARS
# ============================================================

def extract_warranty_years(value):

    if value is None:
        return None

    import re

    text = str(value).lower()

    match = re.search(
        r"(\d+(?:\.\d+)?)",
        text
    )

    if not match:
        return None

    number = float(
        match.group(1)
    )

    if "month" in text:

        return number / 12

    return number


# ============================================================
# PAYMENT SCORE
# ============================================================

def calculate_payment_score(value):

    if value is None:
        return None

    text = str(value).lower()

    import re

    match = re.search(
        r"(\d+)",
        text
    )

    if not match:
        return 50

    days = int(
        match.group(1)
    )

    if days >= 60:
        return 100

    if days >= 45:
        return 90

    if days >= 30:
        return 80

    if days >= 15:
        return 60

    return 40


# ============================================================
# SCORE VENDORS
# ============================================================

def calculate_scores(
    vendors,
    price_weight,
    delivery_weight,
    warranty_weight,
    payment_weight
):

    rows = []

    for vendor in vendors:

        row = {}

        row["vendor"] = (
            vendor.get("vendor")
            or "Unknown Vendor"
        )

        row["currency"] = (
            vendor.get("currency")
            or ""
        )

        row["total_price"] = (
            get_total_price(vendor)
        )

        row["delivery_days"] = (
            extract_delivery_days(
                vendor.get("delivery")
            )
        )

        row["warranty_years"] = (
            extract_warranty_years(
                vendor.get("warranty")
            )
        )

        row["payment_terms"] = (
            vendor.get("payment_terms")
            or "Not specified"
        )

        row["quotation_number"] = (
            vendor.get("quotation_number")
        )

        row["raw_data"] = vendor

        rows.append(row)

    df = pd.DataFrame(rows)

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    if df["total_price"].notna().any():

        minimum_price = (
            df["total_price"]
            .dropna()
            .min()
        )

        df["price_score"] = (
            minimum_price
            / df["total_price"]
            * 100
        )

    else:

        df["price_score"] = None

    # --------------------------------------------------------
    # DELIVERY
    # --------------------------------------------------------

    if df["delivery_days"].notna().any():

        minimum_delivery = (
            df["delivery_days"]
            .dropna()
            .min()
        )

        df["delivery_score"] = (
            minimum_delivery
            / df["delivery_days"]
            * 100
        )

    else:

        df["delivery_score"] = None

    # --------------------------------------------------------
    # WARRANTY
    # --------------------------------------------------------

    if df["warranty_years"].notna().any():

        maximum_warranty = (
            df["warranty_years"]
            .dropna()
            .max()
        )

        if maximum_warranty > 0:

            df["warranty_score"] = (
                df["warranty_years"]
                / maximum_warranty
                * 100
            )

        else:

            df["warranty_score"] = None

    else:

        df["warranty_score"] = None

    # --------------------------------------------------------
    # PAYMENT
    # --------------------------------------------------------

    df["payment_score"] = (
        df["payment_terms"]
        .apply(calculate_payment_score)
    )

    # --------------------------------------------------------
    # DYNAMIC WEIGHTED SCORE
    # --------------------------------------------------------

    scores = []

    for _, row in df.iterrows():

        available_scores = []
        available_weights = []

        if pd.notna(
            row["price_score"]
        ):

            available_scores.append(
                row["price_score"]
            )

            available_weights.append(
                price_weight
            )

        if pd.notna(
            row["delivery_score"]
        ):

            available_scores.append(
                row["delivery_score"]
            )

            available_weights.append(
                delivery_weight
            )

        if pd.notna(
            row["warranty_score"]
        ):

            available_scores.append(
                row["warranty_score"]
            )

            available_weights.append(
                warranty_weight
            )

        if pd.notna(
            row["payment_score"]
        ):

            available_scores.append(
                row["payment_score"]
            )

            available_weights.append(
                payment_weight
            )

        if not available_scores:

            scores.append(0)

            continue

        total_available_weight = sum(
            available_weights
        )

        weighted_score = sum(
            score * weight
            for score, weight
            in zip(
                available_scores,
                available_weights
            )
        )

        weighted_score /= (
            total_available_weight
        )

        scores.append(
            round(
                weighted_score,
                2
            )
        )

    df["overall_score"] = scores

    return df


# ============================================================
# PURCHASE ORDER GENERATOR
# ============================================================

def generate_purchase_order(
    vendor_row
):

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4
    )

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "<b>PURCHASE ORDER</b>",
            styles["Title"]
        )
    )

    elements.append(
        Spacer(
            1,
            20
        )
    )

    details = [
        [
            "PO Number",
            "PO-2026-001"
        ],

        [
            "Vendor",
            str(
                vendor_row["vendor"]
            )
        ],

        [
            "Quotation Number",
            str(
                vendor_row[
                    "quotation_number"
                ]
                or "-"
            )
        ],

        [
            "Total Price",
            f"{vendor_row['currency']} "
            f"{vendor_row['total_price']:,.2f}"
        ],

        [
            "Delivery",
            f"{vendor_row['delivery_days'] or 'Not specified'} days"
        ],

        [
            "Warranty",
            f"{vendor_row['warranty_years'] or 'Not specified'} years"
        ],

        [
            "Payment Terms",
            str(
                vendor_row[
                    "payment_terms"
                ]
            )
        ]
    ]

    table = Table(
        details,
        colWidths=[
            170,
            280
        ]
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    1,
                    colors.grey
                ),

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.lightgrey
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold"
                ),

                (
                    "PADDING",
                    (0, 0),
                    (-1, -1),
                    8
                )
            ]
        )
    )

    elements.append(table)

    elements.append(
        Spacer(
            1,
            30
        )
    )

    elements.append(
        Paragraph(
            "Generated by ProcureAI",
            styles["Normal"]
        )
    )

    document.build(
        elements
    )

    buffer.seek(0)

    return buffer


# ============================================================
# HEADER
# ============================================================

st.title(
    "🏢 ProcureAI"
)

st.subheader(
    "AI-Powered Procurement Decision Engine"
)

st.write(
    "Analyze RFQs and vendor quotations "
    "from different organizations, products "
    "and services."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ Procurement Priorities"
    )

    price_weight = st.slider(
        "💰 Price",
        0,
        100,
        40
    )

    delivery_weight = st.slider(
        "🚚 Delivery",
        0,
        100,
        25
    )

    warranty_weight = st.slider(
        "🛡 Warranty",
        0,
        100,
        20
    )

    payment_weight = st.slider(
        "💳 Payment Terms",
        0,
        100,
        15
    )

    total_weight = (
        price_weight
        + delivery_weight
        + warranty_weight
        + payment_weight
    )

    st.write(
        f"**Total: {total_weight}%**"
    )

    if total_weight != 100:

        st.warning(
            "Adjust the sliders so the total is 100%."
        )

    st.divider()

    st.info(
        "Missing quotation information "
        "is not automatically treated as zero. "
        "Available criteria are normalized."
    )


# ============================================================
# RFQ UPLOAD
# ============================================================

st.header(
    "1️⃣ Upload RFQ"
)

rfq_file = st.file_uploader(
    "Upload the organization's RFQ",
    type=["pdf"],
    key="rfq"
)


# ============================================================
# QUOTATION UPLOAD
# ============================================================

st.header(
    "2️⃣ Upload Vendor Quotations"
)

quotation_files = st.file_uploader(
    "Upload one or more vendor quotation PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    key="quotations"
)


# ============================================================
# ANALYZE
# ============================================================

if st.button(
    "🚀 Analyze Procurement",
    type="primary"
):

    if rfq_file is None:

        st.error(
            "Please upload an RFQ."
        )

        st.stop()

    if not quotation_files:

        st.error(
            "Please upload at least one quotation."
        )

        st.stop()

    if total_weight != 100:

        st.error(
            "Procurement weights must total 100%."
        )

        st.stop()

    # --------------------------------------------------------
    # RFQ EXTRACTION
    # --------------------------------------------------------

    with st.spinner(
        "📄 Reading RFQ..."
    ):

        rfq_text = extract_pdf_text(
            rfq_file
        )

    if not rfq_text.strip():

        st.error(
            "Could not extract text from the RFQ."
        )

        st.stop()

    st.success(
        "RFQ successfully read."
    )

    # --------------------------------------------------------
    # PROCESS QUOTATIONS
    # --------------------------------------------------------

    vendors = []

    progress = st.progress(0)

    errors = []

    for index, quotation in enumerate(
        quotation_files
    ):

        with st.spinner(
            f"🤖 AI analyzing {quotation.name}..."
        ):

            try:

                text = extract_pdf_text(
                    quotation
                )

                if not text.strip():

                    errors.append(
                        f"{quotation.name}: "
                        "No readable text found."
                    )

                    continue

                vendor_data = (
                    extract_vendor_data(
                        text
                    )
                )

                vendors.append(
                    vendor_data
                )
                
                # ========================================================
                # RFQ COMPLIANCE ANALYSIS
                # ========================================================

                for vendor in vendors:

                    vendor["compliance"] = analyze_compliance(
                        rfq_text,
                        vendor_data
                    )

            except Exception as e:

                errors.append(
                    f"{quotation.name}: {str(e)}"
                )

        progress.progress(
            (index + 1)
            / len(quotation_files)
        )

    if errors:

        st.warning(
            "Some documents could not be processed."
        )

        for error in errors:

            st.write(
                f"⚠️ {error}"
            )

    if not vendors:

        st.error(
            "No quotation data could be extracted."
        )

        st.stop()

    # --------------------------------------------------------
    # VENDOR SCORING
    # --------------------------------------------------------

    df = calculate_scores(
        vendors,
        price_weight,
        delivery_weight,
        warranty_weight,
        payment_weight
    )

    # Remove vendors with no usable score

    df = df[
        df["overall_score"] > 0
    ].reset_index(
        drop=True
    )

    if df.empty:

        st.error(
            "No vendors contain enough "
            "information for comparison."
        )

        st.stop()

    # --------------------------------------------------------
    # BEST VENDOR
    # --------------------------------------------------------

    best_index = (
        df["overall_score"]
        .idxmax()
    )

    best_vendor = df.loc[
        best_index
    ]

    # ========================================================
    # RESULTS
    # ========================================================

    st.divider()

    st.header(
        "3️⃣ Procurement Analysis"
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Vendors Analyzed",
            len(df)
        )

    with col2:

        st.metric(
            "Best Score",
            f"{best_vendor['overall_score']}/100"
        )

    with col3:

        st.metric(
            "Recommended Vendor",
            best_vendor["vendor"]
        )

    with col4:

        if pd.notna(
            best_vendor["total_price"]
        ):

            st.metric(
                "Best Quotation",
                f"{best_vendor['currency']} "
                f"{best_vendor['total_price']:,.0f}"
            )

        else:

            st.metric(
                "Best Quotation",
                "Not available"
            )

    # --------------------------------------------------------
    # COMPARISON TABLE
    # --------------------------------------------------------

    st.subheader(
        "📊 Vendor Comparison"
    )

    display_df = df[
        [
            "vendor",
            "total_price",
            "delivery_days",
            "warranty_years",
            "payment_terms",
            "overall_score"
        ]
    ].copy()

    display_df.columns = [
        "Vendor",
        "Total Price",
        "Delivery (Days)",
        "Warranty (Years)",
        "Payment Terms",
        "Overall Score"
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
    
    # ========================================================
# RFQ COMPLIANCE
# ========================================================

st.divider()

st.header(
    "🔍 RFQ Compliance Analysis"
)

st.write(
    "The system compares vendor quotations "
    "against requirements detected from the RFQ."
)

for vendor in vendors:

    vendor_name = (
        vendor.get("vendor")
        or "Unknown Vendor"
    )

    compliance = vendor.get(
        "compliance",
        {}
    )

    status = compliance.get(
        "status",
        "REVIEW"
    )

    if status == "COMPLIANT":

        st.success(
            f"✅ {vendor_name}: COMPLIANT"
        )

    elif status == "NON-COMPLIANT":

        st.error(
            f"❌ {vendor_name}: NON-COMPLIANT"
        )

    else:

        st.warning(
            f"⚠️ {vendor_name}: REVIEW REQUIRED"
        )

    checks = compliance.get(
        "checks",
        []
    )

    if checks:

        compliance_df = pd.DataFrame(
            checks
        )

        st.dataframe(
            compliance_df,
            use_container_width=True,
            hide_index=True
        )

    st.write(
        compliance.get(
            "message",
            ""
        )
    )

    