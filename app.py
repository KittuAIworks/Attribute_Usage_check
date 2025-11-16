import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Enhanced Syndigo Attribute Checker", layout="wide")

st.title("Enhanced Syndigo Attribute Usage Checker")

# --- Upload Excel File ---
st.markdown("### 📂 Upload Data Model")
uploaded_file = st.file_uploader("Upload the Data Model Excel file", type=["xlsx"])

if uploaded_file:
    # Read Excel sheets
    metadata_df = pd.read_excel(uploaded_file, sheet_name="METADATA", engine="openpyxl", header=None)
    ear_model_df = pd.read_excel(uploaded_file, sheet_name="E-A-R MODEL", engine="openpyxl")

    # Extract tenant name
    tenant_name = metadata_df.iloc[6, 1]
    st.success(f"✅ Tenant detected: **{tenant_name}**")

    # Extract entities and attributes
    entity_attr_map = {}
    for entity, attr in zip(ear_model_df["ENTITY"], ear_model_df["MAPPED ATTRIBUTE"]):
        if pd.notna(entity) and pd.notna(attr):
            entity_attr_map.setdefault(entity, set()).add(attr)

    # Convert sets to lists
    for entity in entity_attr_map:
        entity_attr_map[entity] = sorted(entity_attr_map[entity])

    # Dropdown for entity selection
    entity_options = ["All Entities"] + sorted(entity_attr_map.keys())
    selected_entity = st.selectbox("Select Entity", entity_options, index=0)

    # --- Authentication Details ---
    st.markdown("### 🔐 Authentication Details")
    col1, col2, col3 = st.columns(3)
    with col1:
        user_id = st.text_input("User ID", value="system")
    with col2:
        client_id = st.text_input("Client ID")
    with col3:
        client_secret = st.text_input("Client Secret")

    # --- Submit Button ---
    if st.button("🚀 Generate Report"):
        if not all([client_id, client_secret]):
            st.error("⚠️ Please provide authentication details.")
        else:
            # Prepare entities to process
            entities_to_process = entity_attr_map.keys() if selected_entity == "All Entities" else [selected_entity]

            # Prepare API headers
            API_URL_TEMPLATE = f"https://{tenant_name}.syndigo.com/api/entityappservice/get"
            headers = {
                "Content-Type": "application/json",
                "x-rdp-version": "8.1",
                "x-rdp-clientId": "rdpclient",
                "x-rdp-userId": user_id,
                "auth-client-id": client_id,
                "auth-client-secret": client_secret
            }

            results = []
            progress = st.progress(0)
            status_text = st.empty()

            def process_attribute(entity, attribute):
                body = {
                    "params": {
                        "query": {
                            "filters": {
                                "typesCriterion": [entity],
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
                    response = requests.post(API_URL_TEMPLATE, json=body, headers=headers)
                    if response.status_code == 200:
                        response_json = response.json()
                        count = response_json.get("response", {}).get("totalRecords", 0)
                        entities = response_json.get("response", {}).get("entities", [])
                        if entities:
                            attr_obj = entities[0].get("data", {}).get("attributes", {}).get(attribute, {})
                            if isinstance(attr_obj, dict):
                                if "group" in attr_obj:
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
                                elif "values" in attr_obj:
                                    vals = attr_obj["values"]
                                    if vals and isinstance(vals[0], dict):
                                        sample_value = vals[0].get("value", "")
                    else:
                        count = f"Error {response.status_code}"
                except Exception as e:
                    count = f"Error: {str(e)}"
                return {"Entity": entity, "Attribute": attribute, "Attribute Type": attr_type, "Count": count, "Sample Data": sample_value}

            # Multi-threaded execution
            all_tasks = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                for entity in entities_to_process:
                    for attribute in entity_attr_map[entity]:
                        all_tasks.append(executor.submit(process_attribute, entity, attribute))

                completed = 0
                total = len(all_tasks)
                for future in as_completed(all_tasks):
                    results.append(future.result())
                    completed += 1
                    progress.progress(completed / total)
                    status_text.text(f"Processed {completed}/{total} attributes")

            # Prepare DataFrame
            result_df = pd.DataFrame(results)
            st.success("✅ Report generation complete!")
            st.dataframe(result_df, use_container_width=True)

            # Download buttons
            csv = result_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, "attribute_usage_report.csv", "text/csv")

            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                result_df.to_excel(writer, index=False, sheet_name='Report')
            st.download_button("📊 Download Excel", excel_buffer.getvalue(), "attribute_usage_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
