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
from io import BytesIO
import sqlite3
import subprocess
from datetime import datetime
from pdf2image import convert_from_path

# ------------------ APP CONFIG ------------------
st.set_page_config(page_title="Certificate Generator", layout="wide")
st.markdown(
    """
    <style>
    :root {
        --cg-text-light: #1f2937;
        --cg-text-dark: #e5e7eb;
        --cg-card-light: #f3f7fb;
        --cg-card-light-2: #eef4fa;
        --cg-border-light: #cfd9e6;
        --cg-card-dark: #1e293b;
        --cg-card-dark-2: #243447;
        --cg-border-dark: #3b4f66;
    }
    .app-title {
        color: var(--cg-text-light);
        margin-bottom: 0.25rem;
    }
    .top-info-card {
        background: var(--cg-card-light);
        border: 1px solid var(--cg-border-light);
        border-left: 5px solid #6b8fb1;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
        color: var(--cg-text-light);
    }
    .top-info-card h4,
    .top-info-card p {
        color: inherit;
    }
    .upload-guide-card {
        background: var(--cg-card-light-2);
        border: 1px solid var(--cg-border-light);
        border-left: 5px solid #6b8fb1;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
        color: var(--cg-text-light);
    }
    .trust-card {
        background: #f5f8fc;
        border: 1px solid var(--cg-border-light);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 10px;
        color: var(--cg-text-light);
        font-size: 15px;
    }
    @media (prefers-color-scheme: dark) {
        .app-title {
            color: var(--cg-text-dark);
        }
        .top-info-card {
            background: var(--cg-card-dark);
            border-color: var(--cg-border-dark);
            color: var(--cg-text-dark);
        }
        .upload-guide-card {
            background: var(--cg-card-dark-2);
            border-color: var(--cg-border-dark);
            color: var(--cg-text-dark);
        }
        .trust-card {
            background: #202f44;
            border-color: var(--cg-border-dark);
            color: var(--cg-text-dark);
        }
    }
        .app-footer {
            margin-top: 24px;
            padding-top: 12px;
            border-top: 1px solid var(--cg-border-light);
            text-align: center;
            color: #475569;
            font-size: 14px;
        }
        @media (prefers-color-scheme: dark) {
            .app-footer {
                border-top-color: var(--cg-border-dark);
                color: #cbd5e1;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown("<h1 class='app-title'>🎓 Certificate Generator</h1>", unsafe_allow_html=True)
st.markdown(
    """
    <div class='top-info-card'>
    <h4 style='margin:0 0 8px 0;'>How to Use</h4>
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

# Sample assets are used by default and can be replaced by uploads.
SAMPLE_TEMPLATE_PATH = "SAMPLE CERTIFICATE.png"
SAMPLE_EXCEL_PATH = "Name_list.xlsx"
SAMPLE_SIGN_PATH = "SAMPLE SIGN.png"

# ------------------ FILE UPLOADS ------------------
st.markdown(
    """
    <div class='upload-guide-card'>
    <p style='font-size:17px; margin:0;'>Default files are loaded. You can replace the certificate, replace the list, and replace the sign below.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

col_cert, col_list, col_sign = st.columns(3)
with col_cert:
    st.markdown("#### Replace Certificate")
    template_file = st.file_uploader(
        "Upload certificate template",
        type=["jpg", "jpeg", "png", "pdf"],
        key="template_upload",
        help="Upload JPG/PNG/PDF to replace the default certificate template.",
    )

with col_list:
    st.markdown("#### Replace List")
    excel_file = st.file_uploader(
        "Upload participant list",
        type=["xlsx", "xls", "csv"],
        key="excel_upload",
        help="Upload Excel/CSV with a required 'Name' column.",
    )

    if os.path.exists(SAMPLE_EXCEL_PATH):
        with open(SAMPLE_EXCEL_PATH, "rb") as f:
            sample_sheet_data = f.read()
        sample_sheet_name = "sample_name_list.xlsx"
    else:
        sample_df = pd.DataFrame({"Name": ["Participant One", "Participant Two"]})
        sample_buffer = BytesIO()
        sample_df.to_excel(sample_buffer, index=False)
        sample_sheet_data = sample_buffer.getvalue()
        sample_sheet_name = "sample_name_list.xlsx"

    st.download_button(
        "Download Sample List",
        data=sample_sheet_data,
        file_name=sample_sheet_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with col_sign:
    st.markdown("#### Replace Sign")
    sign_files = st.file_uploader(
        "Upload signature image(s)",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="sign_upload",
        help="Upload one or more signature files to replace the default sign.",
    )

active_template_input = template_file if template_file is not None else (SAMPLE_TEMPLATE_PATH if os.path.exists(SAMPLE_TEMPLATE_PATH) else None)
active_excel_input = excel_file if excel_file is not None else (SAMPLE_EXCEL_PATH if os.path.exists(SAMPLE_EXCEL_PATH) else None)
active_sign_inputs = list(sign_files) if sign_files else ([SAMPLE_SIGN_PATH] if os.path.exists(SAMPLE_SIGN_PATH) else [])

st.info("Default template/list/sign are loaded. Replace any of them using the three sections above. If no sign is required, turn off 'Use Signatures' in sidebar.")
template_source_label = template_file.name if template_file is not None else ("SAMPLE CERTIFICATE.png" if active_template_input else "Not selected")
excel_source_label = excel_file.name if excel_file is not None else ("Name_list.xlsx" if active_excel_input else "Not selected")
sign_source_label = "Uploaded signs" if sign_files else ("SAMPLE SIGN.png" if active_sign_inputs else "Not selected")
st.caption(f"Current sources -> Template: {template_source_label} | Data: {excel_source_label} | Signatures: {sign_source_label}")
st.markdown(
    """
    <div class='trust-card'>
    <b>Built by NFSU Goa Coding Club.</b><br>
    Your uploaded files are used only for certificate generation in the current session and are not stored as permanent user data on this platform.
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------ SIDEBAR SETTINGS ------------------
st.sidebar.header("⚙️ Settings")

# Name placement
name_x = st.sidebar.number_input("Name X Position (Left/Right)", value=80, key="name_x")
name_y = st.sidebar.number_input("Name Y Position", value=105, key="name_y")
st.sidebar.caption("Adjust Name X to move text left or right on the certificate.")
font_family = st.sidebar.selectbox("Font Family", ["Times", "Arial", "Courier", "Helvetica"])
font_size = st.sidebar.number_input("Font Size", value=34)
name_color = st.sidebar.color_picker("Name Font Color", value="#111111")

# Certificate numbering
enable_number = st.sidebar.checkbox("Enable Certificate Numbering")
number_font_family = st.sidebar.selectbox(
    "Number Font Family",
    ["Times", "Arial", "Courier", "Helvetica"],
    index=1,
)
number_font_style_label = st.sidebar.selectbox(
    "Number Font Style",
    ["Regular", "Bold", "Italic", "Bold Italic"],
    index=1,
)
number_font_size = st.sidebar.number_input("Number Font Size", value=14, min_value=8, max_value=72)
number_color = st.sidebar.color_picker("Number Font Color", value="#111111")
if "number_prefix" not in st.session_state:
    st.session_state["number_prefix"] = ""
if enable_number:
    preview_weight = "700" if "Bold" in number_font_style_label else "400"
    preview_style = "italic" if "Italic" in number_font_style_label else "normal"
    st.sidebar.markdown(
        f"<div style='font-family:{number_font_family}; font-size:{int(number_font_size)}px; color:{number_color}; font-weight:{preview_weight}; font-style:{preview_style}; margin-bottom:6px;'><b>Numbering preview:</b> {st.session_state['number_prefix']}001</div>",
        unsafe_allow_html=True,
    )
number_prefix = st.sidebar.text_input("Number Prefix (optional)", key="number_prefix")
number_y = st.sidebar.number_input("Number Y Position", value=20, key="number_y")
number_x = st.sidebar.number_input("Number X Position", value=250, key="number_x")

# Signatures
use_signatures = st.sidebar.checkbox("Use Signatures", value=True)
sign_positions = []
if use_signatures and active_sign_inputs:
    st.sidebar.subheader("Signatures Settings")
    for i, _ in enumerate(active_sign_inputs):
        with st.sidebar.expander(f"Signature {i+1}"):
            sx = st.number_input(f"X pos (Sign {i+1})", value=50 + i * 80, key=f"sx_{i}")
            sy = st.number_input(f"Y pos (Sign {i+1})", value=150, key=f"sy_{i}")
            sw = st.number_input(f"Width (Sign {i+1})", value=40, key=f"sw_{i}")
            keep = st.checkbox(f"Include Sign {i+1}", value=True, key=f"keep_{i}")
            if keep:
                sign_positions.append((sx, sy, sw))

# ------------------ HELPERS ------------------
VISITOR_DB_PATH = "visitor_count.db"

def save_uploaded_file_to_tmp(uploaded_file):
    if isinstance(uploaded_file, str):
        return uploaded_file

    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.read())
    tmp.close()
    return tmp.name

def hex_to_rgb(hex_color):
    """Convert #RRGGBB hex color to RGB tuple for FPDF."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_last_updated_date():
    """Read latest Git commit date; fallback to app.py modified date."""
    try:
        output = subprocess.check_output(
            ["git", "log", "-1", "--format=%cs"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if output:
            return output
    except Exception:
        pass

    modified_ts = os.path.getmtime(__file__)
    return datetime.fromtimestamp(modified_ts).strftime("%Y-%m-%d")

def get_or_create_visitor_count():
    """Persist and increment visitor count once per browser session."""
    conn = sqlite3.connect(VISITOR_DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        cursor.execute("SELECT count FROM stats WHERE id = 1")
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO stats (id, count) VALUES (1, 0)")
            conn.commit()

        if "visitor_counted" not in st.session_state:
            cursor.execute("UPDATE stats SET count = count + 1 WHERE id = 1")
            st.session_state["visitor_counted"] = True
            conn.commit()

        cursor.execute("SELECT count FROM stats WHERE id = 1")
        return cursor.fetchone()[0]
    finally:
        conn.close()

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

def prepare_template_image(template_input):
    """Return an image path for template input (supports image or PDF)."""
    template_path = save_uploaded_file_to_tmp(template_input)
    ext = os.path.splitext(template_path)[1].lower()

    if ext != ".pdf":
        return template_path

    out_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    out_png.close()

    try:
        import fitz  # PyMuPDF
        with fitz.open(template_path) as doc:
            if len(doc) == 0:
                raise RuntimeError("PDF template has no pages.")
            pix = doc[0].get_pixmap(alpha=False)
            pix.save(out_png.name)
        return out_png.name
    except Exception:
        poppler_path = get_poppler_path()
        kwargs = {"first_page": 1, "last_page": 1}
        if poppler_path:
            kwargs["poppler_path"] = poppler_path
        pages = convert_from_path(template_path, **kwargs)
        pages[0].save(out_png.name, format="PNG")
        return out_png.name

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
if active_template_input and active_excel_input:
    try:
        if isinstance(active_excel_input, str) and active_excel_input.lower().endswith(".csv"):
            df = pd.read_csv(active_excel_input)
        elif not isinstance(active_excel_input, str) and active_excel_input.name.lower().endswith(".csv"):
            df = pd.read_csv(active_excel_input)
        else:
            df = pd.read_excel(active_excel_input)
    except Exception as e:
        st.error(f"❌ Error reading Excel: {e}")
        st.stop()

    if "Name" not in df.columns:
        st.error("❌ Excel must contain a column named 'Name'.")
        st.stop()

    names = df['Name'].dropna().astype(str).tolist()
    st.success("✅ Files uploaded successfully!")
    name_rgb = hex_to_rgb(name_color)
    number_rgb = hex_to_rgb(number_color)
    number_style_map = {
        "Regular": "",
        "Bold": "B",
        "Italic": "I",
        "Bold Italic": "BI",
    }
    number_font_style = number_style_map[number_font_style_label]

    # Save template & signatures
    try:
        template_path = prepare_template_image(active_template_input)
    except Exception as e:
        st.error(f"❌ Could not process certificate template: {e}")
        st.stop()

    sign_paths = [save_uploaded_file_to_tmp(s) for s in active_sign_inputs] if (use_signatures and active_sign_inputs) else []

    # ------------------ PREVIEW ------------------
    st.markdown("### Preview Certificate")
    st.caption("All names from your list are loaded here. Use the dropdown to switch and preview any name.")

    if names:
        test_name = st.selectbox(
            "🔍 Select name for preview",
            options=names,
            index=0,
            help="The first name is selected by default. Choose another name from the dropdown to preview changes.",
        )

        page_width = 297  # A4 landscape
        preview_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        preview_pdf.close()

        pdf = FPDF('L', 'mm', 'A4')
        pdf.add_page()
        pdf.image(template_path, x=0, y=0, w=297, h=210)

        # Add name
        pdf.set_text_color(*name_rgb)
        pdf.set_font(font_family, '', int(font_size))
        pdf.text(x=float(name_x), y=float(name_y), txt=test_name)

        # Add number
        if enable_number:
            pdf.set_text_color(*number_rgb)
            pdf.set_font(number_font_family, number_font_style, int(number_font_size))
            cert_no = f"{number_prefix}001"
            pdf.text(x=number_x, y=number_y, txt=cert_no)

        pdf.set_text_color(0, 0, 0)

        # Add signatures
        for sign_path, pos in zip(sign_paths, sign_positions):
            sx, sy, sw = pos
            pdf.image(sign_path, x=float(sx), y=float(sy), w=float(sw))

        pdf.output(preview_pdf.name)

        # Show inline preview
        preview_image = None
        try:
            with st.spinner("Generating preview..."):
                poppler_path = get_poppler_path()
                convert_kwargs = {"dpi": 150, "first_page": 1, "last_page": 1}
                if poppler_path:
                    convert_kwargs["poppler_path"] = poppler_path

                pages = convert_from_path(preview_pdf.name, **convert_kwargs)
            preview_image = pages[0]
        except Exception:
            pymupdf_image = render_preview_with_pymupdf(preview_pdf.name)
            if pymupdf_image is not None:
                preview_image = pymupdf_image
                st.caption("Preview rendered using PyMuPDF fallback (Poppler not required).")
            else:
                st.warning("⚠️ Image preview unavailable. Showing embedded PDF preview instead.")
                show_pdf_fallback_preview(preview_pdf.name)
                st.caption(
                    "Tip (Windows): install Poppler and set POPPLER_PATH to its 'Library\\bin' folder "
                    "for faster image-based preview."
                )

        if preview_image is not None:
            st.image(preview_image, caption=f"📄 Preview: {test_name}", use_container_width=True)

        # Download preview
        with open(preview_pdf.name, "rb") as f:
            st.download_button("⬇️ Download Preview", f, file_name="preview_test.pdf")
    else:
        st.warning("No names found in the uploaded list. Add values in the Name column to preview certificates.")

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
                pdf.set_text_color(*name_rgb)
                pdf.set_font(
                    font_family,
                    '',
                    int(font_size)
                )
        
                pdf.text(
                    x=float(name_x),
                    y=float(name_y),
                    txt=str(name)
                )
        
                # Certificate Number
                if enable_number:
                    pdf.set_text_color(*number_rgb)
                    pdf.set_font(number_font_family, number_font_style, int(number_font_size))
                    pdf.text(x=number_x, y=number_y, txt=cert_no)

                pdf.set_text_color(0, 0, 0)

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
                merged_pdf.set_text_color(*name_rgb)
                merged_pdf.set_font(font_family, '', int(font_size))
                merged_pdf.text(x=float(name_x), y=float(name_y), txt=str(name))

                # Number
                if enable_number:
                    merged_pdf.set_text_color(*number_rgb)
                    merged_pdf.set_font(number_font_family, number_font_style, int(number_font_size))
                    merged_pdf.text(x=number_x, y=number_y, txt=cert_no)

                merged_pdf.set_text_color(0, 0, 0)

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

last_updated = get_last_updated_date()
visitor_count = get_or_create_visitor_count()
st.markdown(
    f"<div class='app-footer'>Built by NFSU Goa Coding Club | Last updated: {last_updated} | Visitors: {visitor_count}</div>",
    unsafe_allow_html=True,
)
