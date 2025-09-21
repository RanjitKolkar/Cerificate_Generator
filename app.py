import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import os
import tempfile
import re
import shutil
from pdf2image import convert_from_path

# ------------------ APP CONFIG ------------------
st.set_page_config(page_title="Certi Gen", layout="wide")
st.markdown("<h1 style='color:#2E86C1;'>🎓 Certify Pro+</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='color:#117A65;'>Smart certificate generator with numbering & custom fields</h4>", unsafe_allow_html=True)

# ------------------ FILE UPLOADS ------------------
template_file = st.file_uploader("📄 Upload Certificate Template (JPG/PNG)", type=["jpg", "jpeg", "png"])
excel_file = st.file_uploader("📊 Upload Excel File (must have 'Name' column)", type=["xlsx"])
sign_files = st.file_uploader("✍️ Upload Signature Images (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

# ------------------ SIDEBAR SETTINGS ------------------
st.sidebar.header("⚙️ Settings")

# Name placement
name_y = st.sidebar.number_input("Name Y Position", value=105)
font_family = st.sidebar.selectbox("Font Family", ["Times", "Arial", "Courier", "Helvetica"])
font_size = st.sidebar.number_input("Font Size", value=32)

# Certificate numbering
enable_number = st.sidebar.checkbox("Enable Certificate Numbering")
number_prefix = st.sidebar.text_input("Number Prefix", "CERT-")
number_y = st.sidebar.number_input("Number Y Position", value=20)
number_x = st.sidebar.number_input("Number X Position", value=250)

# Signatures
sign_positions = []
if sign_files:
    st.sidebar.subheader("Signatures Settings")
    for i, _ in enumerate(sign_files):
        with st.sidebar.expander(f"Signature {i+1}"):
            sx = st.number_input(f"X pos (Sign {i+1})", value=50 + i * 80, key=f"sx_{i}")
            sy = st.number_input(f"Y pos (Sign {i+1})", value=150, key=f"sy_{i}")
            sw = st.number_input(f"Width (Sign {i+1})", value=40, key=f"sw_{i}")
            keep = st.checkbox(f"Include Sign {i+1}", value=True, key=f"keep_{i}")
            if keep:
                sign_positions.append((sx, sy, sw))

# ------------------ HELPERS ------------------
def save_uploaded_file_to_tmp(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.read())
    tmp.close()
    return tmp.name

# ------------------ MAIN ------------------
if template_file and excel_file:
    try:
        df = pd.read_excel(excel_file)
    except Exception as e:
        st.error(f"❌ Error reading Excel: {e}")
        st.stop()

    if "Name" not in df.columns:
        st.error("❌ Excel must contain a column named 'Name'.")
        st.stop()

    names = df['Name'].dropna().astype(str).tolist()
    st.success("✅ Files uploaded successfully!")

    # Save template & signatures
    template_path = save_uploaded_file_to_tmp(template_file)
    sign_paths = [save_uploaded_file_to_tmp(s) for s in sign_files] if sign_files else []

    # ------------------ PREVIEW ------------------
    test_name = st.selectbox("🔍 Preview with:", ["None"] + names)
    if test_name != "None":
        page_width = 297  # A4 landscape
        preview_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        preview_pdf.close()

        pdf = FPDF('L', 'mm', 'A4')
        pdf.add_page()
        pdf.image(template_path, x=0, y=0, w=297, h=210)

        # Add name
        pdf.set_font(font_family, '', int(font_size))
        pdf.set_xy(0, float(name_y))
        pdf.cell(page_width, 10, txt=test_name, align='C')

        # Add number
        if enable_number:
            pdf.set_font("Arial", 'B', 14)
            cert_no = f"{number_prefix}TEST001"
            pdf.text(x=number_x, y=number_y, txt=cert_no)

        # Add signatures
        for sign_path, pos in zip(sign_paths, sign_positions):
            sx, sy, sw = pos
            pdf.image(sign_path, x=float(sx), y=float(sy), w=float(sw))

        pdf.output(preview_pdf.name)

        # Show inline preview
        try:
            pages = convert_from_path(preview_pdf.name, dpi=150)
            st.image(pages[0], caption=f"📄 Preview: {test_name}", use_column_width=True)
        except Exception:
            st.warning("⚠️ Preview unavailable (Poppler missing).")

        # Download preview
        with open(preview_pdf.name, "rb") as f:
            st.download_button("⬇️ Download Preview", f, file_name="preview_test.pdf")

    # ------------------ GENERATE ALL ------------------
    if st.button("🚀 Generate All Certificates"):
        with tempfile.TemporaryDirectory() as tmpdir:
            page_width = 297
            for idx, name in enumerate(names, start=1):
                pdf = FPDF('L', 'mm', 'A4')
                pdf.add_page()
                pdf.image(template_path, x=0, y=0, w=297, h=210)

                # Name
                pdf.set_font(font_family, '', int(font_size))
                pdf.set_xy(0, float(name_y))
                pdf.cell(page_width, 10, txt=str(name), align='C')

                # Number
                if enable_number:
                    cert_no = f"{number_prefix}{idx:03d}"
                    pdf.set_font("Arial", 'B', 14)
                    pdf.text(x=number_x, y=number_y, txt=cert_no)

                # Signatures
                for sign_path, pos in zip(sign_paths, sign_positions):
                    sx, sy, sw = pos
                    pdf.image(sign_path, x=float(sx), y=float(sy), w=float(sw))

                safe_name = re.sub(r'[^A-Za-z0-9]+', '_', str(name)).strip('_')
                out_path = os.path.join(tmpdir, f"{safe_name}.pdf")
                pdf.output(out_path)

            # Zip them
            zip_path = os.path.join(tmpdir, "certificates.zip")
            shutil.make_archive(zip_path.replace(".zip", ""), 'zip', tmpdir)

            with open(zip_path, "rb") as f:
                st.download_button("⬇️ Download All Certificates (ZIP)", f, file_name="certificates.zip")

        st.success("🎉 All certificates generated successfully!")
