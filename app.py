import streamlit as st
import pandas as pd
import time
from fpdf import FPDF
from PIL import Image
import os
import tempfile
import re
import shutil
import base64
from pdf2image import convert_from_path

# ------------------ APP CONFIG ------------------
st.set_page_config(page_title="Certi Gen", layout="wide")
st.markdown("<h1 style='color:#2E86C1;'>🎓 Certify Pro+</h1>", unsafe_allow_html=True)
st.markdown(
    """
    <div style='background:#F4F9FF; border:1px solid #D6EAF8; border-radius:10px; padding:14px 18px; margin-bottom:10px;'>
    <h4 style='color:#117A65; margin:0 0 8px 0;'>How to Use</h4>
    <p style='font-size:18px; margin:4px 0;'>
    1) Upload a certificate template (JPG/PNG), 2) upload Excel with a <b>Name</b> column, 3) optionally add signatures,
    4) preview one certificate, then generate all.
    </p>
    <p style='font-size:18px; margin:8px 0 4px 0;'><b>Numbering Format:</b> Prefix + 3-digit sequence</p>
    <p style='font-size:17px; margin:4px 0;'>
    Example: CERT001, TRAINING001. Leave prefix blank for plain numbering: 001, 002, 003...
    </p>
    <p style='font-size:17px; margin:8px 0 0 0;'><b>Available Outputs:</b> Single merged PDF + ZIP folder of separate PDFs.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------ FILE UPLOADS ------------------
template_file = st.file_uploader("📄 Upload Certificate Template (JPG/PNG)", type=["jpg", "jpeg", "png"])
excel_file = st.file_uploader("📊 Upload Excel File (must have 'Name' column)", type=["xlsx"])
sign_files = st.file_uploader("✍️ Upload Signature Images (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

# ------------------ SIDEBAR SETTINGS ------------------
st.sidebar.header("⚙️ Settings")

# Name placement
name_y = st.sidebar.number_input("Name Y Position", value=105)
font_family = st.sidebar.selectbox("Font Family", ["Times", "Arial", "Courier", "Helvetica"])
font_size = st.sidebar.number_input("Font Size", value=34)

# Certificate numbering
enable_number = st.sidebar.checkbox("Enable Certificate Numbering")
number_prefix = st.sidebar.text_input("Number Prefix (optional)", "")
number_y = st.sidebar.number_input("Number Y Position", value=20)
number_x = st.sidebar.number_input("Number X Position", value=250)
if enable_number:
    st.sidebar.caption(f"Numbering preview: {number_prefix}001")

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

def get_poppler_path():
    """Return a valid Poppler bin path if available on this machine."""
    env_path = os.getenv("POPPLER_PATH")
    if env_path and os.path.isdir(env_path):
        return env_path

    common_paths = [
        r"C:\\Program Files\\poppler\\Library\\bin",
        r"C:\\Program Files (x86)\\poppler\\Library\\bin",
        r"C:\\poppler\\Library\\bin",
        r"C:\\tools\\poppler\\Library\\bin",
    ]
    for path in common_paths:
        if os.path.isdir(path):
            return path
    return None

def show_pdf_fallback_preview(pdf_path):
    """Fallback preview: display PDF directly in the browser using base64."""
    with open(pdf_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    st.markdown(
        f"""
        <iframe
            src="data:application/pdf;base64,{encoded}"
            width="100%"
            height="650"
            type="application/pdf"
            style="border: 1px solid #ccc; border-radius: 8px;"
        ></iframe>
        """,
        unsafe_allow_html=True,
    )

def render_preview_with_pymupdf(pdf_path, dpi=150):
    """Render first page using PyMuPDF (no Poppler required)."""
    try:
        import fitz  # PyMuPDF
        zoom = dpi / 72
        with fitz.open(pdf_path) as doc:
            if len(doc) == 0:
                return None
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    except Exception:
        return None

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
            pdf.set_font("Arial", 'B', 10)
            cert_no = f"{number_prefix}001"
            pdf.text(x=number_x, y=number_y, txt=cert_no)

        # Add signatures
        for sign_path, pos in zip(sign_paths, sign_positions):
            sx, sy, sw = pos
            pdf.image(sign_path, x=float(sx), y=float(sy), w=float(sw))

        pdf.output(preview_pdf.name)

        # Show inline preview
        try:
            with st.spinner("Generating preview..."):
                poppler_path = get_poppler_path()
                convert_kwargs = {"dpi": 150, "first_page": 1, "last_page": 1}
                if poppler_path:
                    convert_kwargs["poppler_path"] = poppler_path

                pages = convert_from_path(preview_pdf.name, **convert_kwargs)
            st.image(pages[0], caption=f"📄 Preview: {test_name}", use_container_width=True)
        except Exception:
            pymupdf_image = render_preview_with_pymupdf(preview_pdf.name)
            if pymupdf_image is not None:
                st.image(pymupdf_image, caption=f"📄 Preview: {test_name}", use_container_width=True)
                st.caption("Preview rendered using PyMuPDF fallback (Poppler not required).")
            else:
                st.warning("⚠️ Image preview unavailable. Showing embedded PDF preview instead.")
                show_pdf_fallback_preview(preview_pdf.name)
                st.caption(
                    "Tip (Windows): install Poppler and set POPPLER_PATH to its 'Library\\bin' folder "
                    "for faster image-based preview."
                )

        # Download preview
        with open(preview_pdf.name, "rb") as f:
            st.download_button("⬇️ Download Preview", f, file_name="preview_test.pdf")

    # ------------------ GENERATE ALL ------------------
    if st.button("🚀 Generate Certificates"):
        status_df = pd.DataFrame({
            "Name": names,
            "Status": ["⏳ Pending"] * len(names)
        })

        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        current_status = st.empty()

        status_placeholder.dataframe(
            status_df,
            use_container_width=True,
            height=400
        )

        start_time = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:
            total = len(names)
            page_width = 297
            individual_dir = os.path.join(tmpdir, "individual_certificates")
            os.makedirs(individual_dir, exist_ok=True)
            merged_pdf = FPDF('L', 'mm', 'A4')

            for idx, name in enumerate(names, start=1):
                cert_no = f"{number_prefix}{idx:03d}"

                current_status.info(
                    f"Generating {idx}/{total}: {name}"
                )

                # Individual PDF
                pdf = FPDF('L', 'mm', 'A4')
                pdf.add_page()
        
                pdf.image(
                    template_path,
                    x=0,
                    y=0,
                    w=297,
                    h=210
                )
        
                # Name
                pdf.set_font(
                    font_family,
                    '',
                    int(font_size)
                )
        
                pdf.set_xy(
                    0,
                    float(name_y)
                )
        
                pdf.cell(
                    page_width,
                    10,
                    txt=str(name),
                    align='C'
                )
        
                # Certificate Number
                if enable_number:
                    pdf.set_font("Arial", 'B', 14)
                    pdf.text(x=number_x, y=number_y, txt=cert_no)

                # Signatures
                for sign_path, pos in zip(
                    sign_paths,
                    sign_positions
                ):
        
                    sx, sy, sw = pos
                    pdf.image(sign_path, x=float(sx), y=float(sy), w=float(sw))

                safe_name = re.sub(r'[^A-Za-z0-9]+', '_', str(name)).strip('_')
                out_path = os.path.join(individual_dir, f"{safe_name}.pdf")
                pdf.output(out_path)

                # Merged single PDF (one page per certificate)
                merged_pdf.add_page()
                merged_pdf.image(template_path, x=0, y=0, w=297, h=210)

                # Name
                merged_pdf.set_font(font_family, '', int(font_size))
                merged_pdf.set_xy(0, float(name_y))
                merged_pdf.cell(page_width, 10, txt=str(name), align='C')

                # Number
                if enable_number:
                    merged_pdf.set_font("Arial", 'B', 14)
                    merged_pdf.text(x=number_x, y=number_y, txt=cert_no)

                # Signatures
                for sign_path, pos in zip(sign_paths, sign_positions):
                    sx, sy, sw = pos
                    merged_pdf.image(sign_path, x=float(sx), y=float(sy), w=float(sw))

                status_df.loc[idx-1, "Status"] = "✅ Completed"
                progress_bar.progress(idx / total)

                if idx % 5 == 0 or idx == total:
                    status_placeholder.dataframe(
                        status_df,
                        use_container_width=True,
                        height=400
                    )

            merged_pdf_path = os.path.join(tmpdir, "all_certificates_merged.pdf")
            merged_pdf.output(merged_pdf_path)

            elapsed = time.time() - start_time

            current_status.success(
                f"🎉 Generated {total} certificates in {elapsed:.2f} seconds"
            )

            # Zip only individual PDFs
            zip_path = os.path.join(tmpdir, "certificates_separate.zip")
            shutil.make_archive(zip_path.replace(".zip", ""), 'zip', individual_dir)

            with open(merged_pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Download All Certificates (Single Merged PDF)",
                    f,
                    file_name="all_certificates_merged.pdf",
                )

            with open(zip_path, "rb") as f:
                st.download_button(
                    "⬇️ Download Separate Certificates (ZIP Folder)",
                    f,
                    file_name="certificates_separate.zip",
                )

        st.success("🎉 Certificates generated! Download merged PDF or separate ZIP.")
