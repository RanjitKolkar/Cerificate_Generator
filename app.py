import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import os
import tempfile
import re
import shutil
from pdf2image import convert_from_path
import base64

st.set_page_config(page_title="Certificate Generator", layout="wide")

st.markdown("<h1 style='color:#2E86C1;'>🎓 Certificate Generator App</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='color:#117A65;'>Automate certificate creation with names & signatures</h4>", unsafe_allow_html=True)

# Uploads
template_file = st.file_uploader("📄 Upload Certificate Template (JPG/PNG)", type=["jpg", "jpeg", "png"])
excel_file = st.file_uploader("📊 Upload Excel File with 'Name' column", type=["xlsx"])
sign_files = st.file_uploader("✍️ Upload Signature Images (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.sidebar.header("⚙️ Placement Settings (units in mm)")
name_y = st.sidebar.number_input("Name Y position (mm)", value=105)   # middle-ish on A4 landscape
font_size = st.sidebar.number_input("Font Size (pt)", value=32)

# signature position inputs (one group per uploaded signature)
sign_positions = []
if sign_files:
    for i, _ in enumerate(sign_files):
        st.sidebar.subheader(f"Signature {i+1}")
        sx = st.sidebar.number_input(f"X position (Sign {i+1})", value=50 + i * 80, key=f"sx_{i}")
        sy = st.sidebar.number_input(f"Y position (Sign {i+1})", value=150, key=f"sy_{i}")
        sw = st.sidebar.number_input(f"Width (Sign {i+1})", value=40, key=f"sw_{i}")
        sign_positions.append((sx, sy, sw))

# helper to save an UploadedFile to a temp file and return the path
def save_uploaded_file_to_tmp(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[1] if hasattr(uploaded_file, "name") else ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    uploaded_file.seek(0)
    tmp.write(uploaded_file.read())
    tmp.flush()
    tmp.close()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    return tmp.name

if template_file and excel_file:
    try:
        df = pd.read_excel(excel_file)
    except Exception as e:
        st.error(f"Error reading Excel: {e}")
        st.stop()

    if "Name" not in df.columns:
        st.error("Excel must contain a column named 'Name'.")
        st.stop()

    names = df['Name'].dropna().astype(str).tolist()
    if len(names) == 0:
        st.error("No valid names found in the 'Name' column.")
        st.stop()

    st.success("✅ Files uploaded successfully!")

    # Save template and signatures to temporary files (so FPDF can read them)
    template_path = save_uploaded_file_to_tmp(template_file)
    sign_paths = [save_uploaded_file_to_tmp(s) for s in sign_files] if sign_files else []

    # Preview single-name selection
    test_name = st.selectbox("🔍 Test with one name first:", ["None"] + names)
    if test_name != "None":
        page_width = 297  # A4 landscape width

        preview_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        preview_pdf.close()
        pdf = FPDF('L', 'mm', 'A4')
        pdf.add_page()
        pdf.image(template_path, x=0, y=0, w=297, h=210)

        # Add name (centered horizontally)
        pdf.set_font("Times", 'B', int(font_size))
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(0, float(name_y))
        pdf.cell(page_width, 10, txt=test_name, align='C')

        # Add signatures
        for sign_path, pos in zip(sign_paths, sign_positions):
            sx, sy, sw = pos
            pdf.image(sign_path, x=float(sx), y=float(sy), w=float(sw))

        pdf.output(preview_pdf.name)

        # Convert first page to image for inline preview
        pages = convert_from_path(preview_pdf.name, dpi=150)
        preview_img_path = preview_pdf.name.replace(".pdf", ".png")
        pages[0].save(preview_img_path, "PNG")
        st.image(preview_img_path, caption=f"📄 Preview: {test_name}", use_column_width=True)

        # Download button
        with open(preview_pdf.name, "rb") as f:
            st.download_button("⬇️ Download Preview", f, file_name="preview_test.pdf")

    # Generate all certificates
    if st.button("🚀 Generate All Certificates"):
        out_dir = "certificates"
        os.makedirs(out_dir, exist_ok=True)

        for name in names:
            pdf = FPDF('L', 'mm', 'A4')
            pdf.add_page()
            pdf.image(template_path, x=0, y=0, w=297, h=210)

            pdf.set_font("Times", 'B', int(font_size))
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(0, float(name_y))
            pdf.cell(page_width, 10, txt=str(name), align='C')

            for sign_path, pos in zip(sign_paths, sign_positions):
                sx, sy, sw = pos
                pdf.image(sign_path, x=float(sx), y=float(sy), w=float(sw))

            safe_name = re.sub(r'[^A-Za-z0-9]+', '_', str(name)).strip('_')
            out_path = os.path.join(out_dir, f"{safe_name}.pdf")
            pdf.output(out_path)

        # make a zip for download
        zip_name = "certificates"
        shutil.make_archive(zip_name, 'zip', out_dir)
        with open(zip_name + ".zip", "rb") as f:
            st.download_button("⬇️ Download All Certificates (zip)", f, file_name="certificates.zip")

        st.success(f"🎉 All certificates generated successfully in '{out_dir}' folder!")
