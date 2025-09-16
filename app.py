import streamlit as st
import pandas as pd
from fpdf import FPDF
import os

# --------------------------
# Utility function to generate preview
# --------------------------
def generate_preview(name, template_path):
    pdf = FPDF("L", "mm", "A4")
    pdf.add_page()

    page_width = 297
    page_height = 210

    img_width_px = 1600
    img_height_px = 1133
    aspect_ratio = img_width_px / img_height_px

    img_width_mm = page_width
    img_height_mm = img_width_mm / aspect_ratio

    if img_height_mm > page_height:
        img_height_mm = page_height
        img_width_mm = img_height_mm * aspect_ratio

    x = (page_width - img_width_mm) / 2
    y = (page_height - img_height_mm) / 2

    pdf.image(template_path, x=x, y=y, w=img_width_mm, h=img_height_mm)

    pdf.set_font("Times", "B", 28)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(0, 85)  # Adjust Y according to template
    pdf.cell(page_width, 10, txt=str(name), align="C")

    return pdf.output(dest="S").encode("latin1")

# --------------------------
# Streamlit App
# --------------------------
st.set_page_config(page_title="Certificate Generator", layout="centered")

st.title("🏆 Certificate Generator")
st.markdown("Upload participant list and a certificate template to generate certificates automatically.")

# File uploaders
uploaded_excel = st.file_uploader("📑 Upload Excel file (must contain column 'Name')", type=["xlsx"])
uploaded_template = st.file_uploader("🖼️ Upload Certificate Template (JPEG/PNG)", type=["jpg", "jpeg", "png"])

if uploaded_excel and uploaded_template:
    try:
        # Read Excel
        df = pd.read_excel(uploaded_excel)
        if "Name" not in df.columns:
            st.error("❌ Excel file must contain a column named **'Name'**.")
            st.stop()

        names = df["Name"].dropna().astype(str).tolist()
        if not names:
            st.error("❌ No names found in the Excel file.")
            st.stop()

        st.success(f"✅ Loaded {len(names)} participants.")

        # Preview dropdown
        selected_name = st.selectbox("👤 Select a participant to preview", names)

        if selected_name:
            try:
                preview_pdf = generate_preview(selected_name, uploaded_template)
                st.download_button(
                    label="⬇️ Download Preview Certificate",
                    data=preview_pdf,
                    file_name=f"{selected_name.replace(' ', '_')}_preview.pdf",
                    mime="application/pdf",
                )
                st.success("✅ Preview ready. The name is visible on the certificate.")

                # Display inline preview
                st.markdown("### 📄 Certificate Preview")
                st.pdf(preview_pdf)

            except Exception as e:
                st.error(f"⚠️ Could not generate preview: {e}")

        # Generate all certificates
        if st.button("🚀 Generate All Certificates"):
            try:
                os.makedirs("certificates", exist_ok=True)

                for name in names:
                    pdf = generate_preview(name, uploaded_template)
                    safe_name = "_".join(name.split())
                    output_path = os.path.join("certificates", f"{safe_name}.pdf")
                    with open(output_path, "wb") as f:
                        f.write(pdf)

                st.success(f"✅ All certificates generated in `certificates/` folder.")

            except Exception as e:
                st.error(f"❌ Error generating certificates: {e}")

    except Exception as e:
        st.error(f"❌ Failed to process files: {e}")
