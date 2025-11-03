import streamlit as st
import pandas as pd
import requests
import io
from PIL import Image

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Syndigo Attribute Count Checker", layout="centered")

# --- Load Logo ---
logo = Image.open("syndigo_logo.png")

# --- Header: Logo + Title Side by Side ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(logo, width=80)
with col_title:
    st.markdown(
        """
        <div style='font-size:30px;font-weight:700;color:#0072CE;'>
            Syndigo Attribute Count Checker
        </div>
        <div style='font-size:15px;color:#666;'>
            Multi-tenant tool to check attribute usage counts via Syndigo API
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- Styling: compact spacing + blue headers + bold labels ---
st.markdown(
    """
    <style>
    /* Compact inputs */
    .stTextInput > div > div > input {
        border-radius: 8px !important;
        border: 1px solid #ccc !important;
        padding: 6px 10px !important;
        margin-top: -6px !important;
    }

    /* Focus border effect */
    .stTextInput > div > div > input:focus {
        border-color: #0072CE !important;
        box-shadow: 0 0 0 1px #0072CE !important;
    }

    /* Buttons */
    .stButton > button {
        background-color: #0072CE !important;
        color: white !important;
        border-radius: 10px !important;
        padding: 0.6em 1.5em !important;
        font-weight: 600 !important;
        border: none !important;
    }
    .stDownloadButton > button {
        background-color: #00A651 !important;
        color: white !important;
        border-radius: 10px !important;
        padding: 0.5em 1.5em !important;
        font-weight: 600 !important;
        border: none !important;
    }

    /* Syndigo blue section headers */
    div[data-testid="stMarkdownContainer"] h3 {
        color: #0072CE !important;
        font-weight: 700 !important;
        margin-top: 0.6rem !important;
        margin-bottom: 0.4rem !important;
    }

    /* Blue bold input labels */
    div[data-testid="InputLabel"] p {
        color: #0072CE !important;
        font-weight: 800 !important;
        font-size: 14px !important;
        margin-bottom: -4px !important;
        line-height: 1.1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Tenant & Entity Section ---
st.markdown("<h3 style='color:#0072CE;font-weight:700;'>🏢 Tenant & Entity Configuration</h3>", unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    st.markdown("<span style='color:#0072CE;font-weight:700;'>Tenant</span>", unsafe_allow_html=True)
    tenant_name = st.text_input("", value="", key="tenant_input", label_visibility="collapsed")
with col2:
    st.markdown("<span style='color:#0072CE;font-weight:700;'>Entity</span>", unsafe_allow_html=True)
    entity_name = st.text_input("", value="", key="entity_input", label_visibility="collapsed")

# --- Authentication Section ---
st.markdown("<h3 style='color:#0072CE;font-weight:700;'>🔐 Authentication Details</h3>", unsafe_allow_html=True)
col3, col4, col5 = st.columns(3)
with col3:
    st.markdown("<span style='color:#0072CE;font-weight:700;'>User ID</span>", unsafe_allow_html=True)
    user_id = st.text_input("", value="system", key="user_input", label_visibility="collapsed")
with col4:
    st.markdown("<span style='color:#0072CE;font-weight:700;'>Client ID</span>", unsafe_allow_html=True)
    client_id = st.text_input("", value="", key="client_input", label_visibility="collapsed")
with col5:
    st.markdown("<span style='color:#0072CE;font-weight:700;'>Client Secret</span>", unsafe_allow_html=True)
    client_secret = st.text_input("", value="", key="secret_input", label_visibility="collapsed")

# --- Submit Button ---
submitted = st.button("🚀 Submit Configuration")

# --- Configuration Handling ---
if submitted:
    if not all([tenant_name, entity_name, client_id, client_secret]):
        st.error("⚠️ Please fill in all required fields before proceeding.")
        st.session_state.configured = False
    else:
        st.session_state.configured = True
        st.session_state.tenant_name = tenant_name
        st.session_state.entity_name = entity_name
        st.session_state.user_id = user_id
        st.session_state.client_id = client_id
        st.session_state.client_secret = client_secret
        st.success(f"✅ Configuration accepted for tenant **{tenant_name}** and entity **{entity_name}**")

# --- Show File Upload Section Only If Configured ---
if st.session_state.get("configured", False):
    st.divider()
    st.markdown("### 📂 Upload Attribute List")
    uploaded_file = st.file_uploader("Upload CSV with one column of attribute names", type=["csv"])

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        if df.shape[1] != 1:
            st.error("CSV must contain exactly one column with attribute names.")
        else:
            attribute_col = df.columns[0]
            attributes = df[attribute_col].dropna().unique().tolist()

            # Prepare API and headers
            API_URL = f"https://{st.session_state.tenant_name}.syndigo.com/api/entityappservice/get"
            headers = {
                "Content-Type": "application/json",
                "x-rdp-version": "8.1",
                "x-rdp-clientId": "rdpclient",
                "x-rdp-userId": st.session_state.user_id,
                "auth-client-id": st.session_state.client_id,
                "auth-client-secret": st.session_state.client_secret
            }

            st.markdown("### ⚙️ Processing Attributes")
            progress = st.progress(0)
            status_text = st.empty()
            results = []

            for i, attribute in enumerate(attributes):
                body = {
                    "params": {
                        "query": {
                            "filters": {
                                "typesCriterion": [st.session_state.entity_name],
                                "attributesCriterion": [{attribute: {"hasvalue": "true"}}],
                                "allContextual": False
                            }
                        },
                        "fields": {"attributes": [attribute]},
                        "options": {"maxRecords": 1}
                    }
                }

                attr_type = "Simple"
                sample_value = ""
                count = ""

                try:
                    response = requests.post(API_URL, json=body, headers=headers)
                    if response.status_code == 200:
                        response_json = response.json()
                        count = response_json.get("response", {}).get("totalRecords", 0)

                        entities = response_json.get("response", {}).get("entities", [])
                        if entities:
                            attr_obj = (
                                entities[0]
                                .get("data", {})
                                .get("attributes", {})
                                .get(attribute, {})
                            )

                            if isinstance(attr_obj, dict):
                                if "group" in attr_obj:  # Non-simple (grouped)
                                    attr_type = "Non Simple"
                                    groups = attr_obj["group"]
                                    for g in groups:
                                        if isinstance(g, dict):
                                            for sub_attr, sub_data in g.items():
                                                if isinstance(sub_data, dict) and "values" in sub_data:
                                                    vals = sub_data["values"]
                                                    if vals and isinstance(vals[0], dict):
                                                        sample_value = vals[0].get("value", "")
                                                        break
                                            if sample_value:
                                                break
                                elif "values" in attr_obj:  # Simple
                                    vals = attr_obj["values"]
                                    if vals and isinstance(vals[0], dict):
                                        sample_value = vals[0].get("value", "")
                    else:
                        count = f"Error {response.status_code}"
                except Exception as e:
                    count = f"Error: {str(e)}"
                    sample_value = ""

                results.append({
                    "Attribute": attribute,
                    "Attribute Type": attr_type,
                    "Count": count,
                    "Sample Data": sample_value
                })

                progress.progress((i + 1) / len(attributes))
                status_text.text(f"Processed {i + 1}/{len(attributes)} attributes")

            result_df = pd.DataFrame(results)
            st.success("✅ Processing complete!")

            st.markdown("### 📊 Results")
            st.dataframe(result_df, use_container_width=True)

            # --- Download Buttons ---
            st.markdown("### 💾 Download Results")
            csv = result_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, "attribute_counts.csv", "text/csv")

            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                result_df.to_excel(writer, index=False, sheet_name='Counts')
            st.download_button(
                "📘 Download Excel",
                excel_buffer.getvalue(),
                "attribute_counts.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
