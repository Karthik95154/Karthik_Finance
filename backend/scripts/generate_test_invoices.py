import os
import io
from PIL import Image, ImageDraw, ImageFont

def generate_sample_invoice_image(
    invoice_number: str,
    invoice_date: str,
    vendor_name: str,
    vendor_gstin: str,
    vendor_address: str,
    customer_name: str,
    customer_gstin: str,
    customer_address: str,
    place_of_supply: str,
    items: list,
    subtotal: float,
    tax_type: str, # "IGST" or "CGST_SGST"
    tax_rate: float,
    total_amount: float,
    output_path: str
):
    """Draws a crisp, high-resolution tax invoice image for VLM processing."""
    width, height = 1200, 1600
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    # Use default font or basic font
    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_header = ImageFont.truetype("arial.ttf", 22)
        font_bold = ImageFont.truetype("arialbd.ttf", 20)
        font_body = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 15)
    except Exception:
        font_title = ImageFont.load_default()
        font_header = font_title
        font_bold = font_title
        font_body = font_title
        font_small = font_title

    # Header Box
    draw.rectangle([(40, 40), (1160, 150)], fill="#f0f4f8", outline="#1e293b", width=2)
    draw.text((60, 55), "TAX INVOICE", fill="#0f172a", font=font_title)
    draw.text((60, 105), f"Original for Recipient | GST Registered Invoice", fill="#475569", font=font_small)

    draw.text((800, 55), f"Invoice #: {invoice_number}", fill="#0f172a", font=font_bold)
    draw.text((800, 85), f"Date: {invoice_date}", fill="#0f172a", font=font_body)
    draw.text((800, 115), f"Due Date: {invoice_date}", fill="#0f172a", font=font_body)

    # Vendor & Customer details box
    y = 170
    draw.rectangle([(40, y), (580, y + 200)], outline="#cbd5e1", width=1)
    draw.rectangle([(620, y), (1160, y + 200)], outline="#cbd5e1", width=1)

    draw.text((55, y + 10), "SUPPLIER / VENDOR DETAILS", fill="#1e293b", font=font_bold)
    draw.text((55, y + 40), f"Name: {vendor_name}", fill="#0f172a", font=font_body)
    draw.text((55, y + 70), f"GSTIN: {vendor_gstin}", fill="#0f172a", font=font_bold)
    draw.text((55, y + 100), f"Address: {vendor_address}", fill="#475569", font=font_body)
    draw.text((55, y + 130), f"State Code: {vendor_gstin[:2]}", fill="#475569", font=font_body)

    draw.text((635, y + 10), "BUYER / CUSTOMER DETAILS", fill="#1e293b", font=font_bold)
    draw.text((635, y + 40), f"Name: {customer_name}", fill="#0f172a", font=font_body)
    draw.text((635, y + 70), f"GSTIN: {customer_gstin}", fill="#0f172a", font=font_bold)
    draw.text((635, y + 100), f"Address: {customer_address}", fill="#475569", font=font_body)
    draw.text((635, y + 130), f"Place of Supply: {place_of_supply}", fill="#0f172a", font=font_bold)

    # Table Header
    ty = 390
    draw.rectangle([(40, ty), (1160, ty + 40)], fill="#e2e8f0", outline="#94a3b8", width=1)
    draw.text((55, ty + 10), "#", fill="#0f172a", font=font_bold)
    draw.text((95, ty + 10), "Item Description", fill="#0f172a", font=font_bold)
    draw.text((480, ty + 10), "HSN/SAC", fill="#0f172a", font=font_bold)
    draw.text((620, ty + 10), "Qty", fill="#0f172a", font=font_bold)
    draw.text((700, ty + 10), "Unit Price", fill="#0f172a", font=font_bold)
    draw.text((850, ty + 10), "Taxable Amt", fill="#0f172a", font=font_bold)
    draw.text((1020, ty + 10), "Total (INR)", fill="#0f172a", font=font_bold)

    # Line Items
    cur_y = ty + 40
    for idx, itm in enumerate(items, 1):
        draw.rectangle([(40, cur_y), (1160, cur_y + 45)], outline="#e2e8f0", width=1)
        draw.text((55, cur_y + 12), str(idx), fill="#334155", font=font_body)
        draw.text((95, cur_y + 12), str(itm["desc"]), fill="#0f172a", font=font_body)
        draw.text((480, cur_y + 12), str(itm.get("hsn", "998313")), fill="#475569", font=font_body)
        draw.text((620, cur_y + 12), str(itm.get("qty", "1.0")), fill="#334155", font=font_body)
        draw.text((700, cur_y + 12), f"Rs. {itm['price']:,.2f}", fill="#334155", font=font_body)
        draw.text((850, cur_y + 12), f"Rs. {itm['taxable']:,.2f}", fill="#0f172a", font=font_bold)
        draw.text((1020, cur_y + 12), f"Rs. {itm['total']:,.2f}", fill="#0f172a", font=font_bold)
        cur_y += 45

    # Summary Totals Box
    sy = cur_y + 30
    draw.rectangle([(650, sy), (1160, sy + 220)], outline="#94a3b8", width=1)
    
    draw.text((670, sy + 15), "Taxable Subtotal:", fill="#334155", font=font_body)
    draw.text((980, sy + 15), f"Rs. {subtotal:,.2f}", fill="#0f172a", font=font_bold)

    if tax_type == "IGST":
        igst_amt = round(subtotal * (tax_rate / 100.0), 2)
        draw.text((670, sy + 50), f"Integrated GST (IGST @ {tax_rate}%):", fill="#334155", font=font_body)
        draw.text((980, sy + 50), f"Rs. {igst_amt:,.2f}", fill="#0f172a", font=font_bold)
    else:
        half_rate = tax_rate / 2.0
        cgst_amt = round(subtotal * (half_rate / 100.0), 2)
        sgst_amt = round(subtotal * (half_rate / 100.0), 2)
        draw.text((670, sy + 45), f"Central GST (CGST @ {half_rate}%):", fill="#334155", font=font_body)
        draw.text((980, sy + 45), f"Rs. {cgst_amt:,.2f}", fill="#0f172a", font=font_bold)
        draw.text((670, sy + 75), f"State GST (SGST @ {half_rate}%):", fill="#334155", font=font_body)
        draw.text((980, sy + 75), f"Rs. {sgst_amt:,.2f}", fill="#0f172a", font=font_bold)

    draw.rectangle([(650, sy + 120), (1160, sy + 175)], fill="#0f172a")
    draw.text((670, sy + 135), "GRAND TOTAL:", fill="white", font=font_bold)
    draw.text((960, sy + 135), f"INR {total_amount:,.2f}", fill="white", font=font_title)

    # Footer
    draw.text((40, 1500), "This is a computer-generated tax invoice for legal and financial processing.", fill="#64748b", font=font_small)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Generated invoice image: {output_path}")

if __name__ == "__main__":
    # 1. Generate Inter-State Invoice
    generate_sample_invoice_image(
        invoice_number="INV-2026-INT-001",
        invoice_date="2026-08-25",
        vendor_name="Apex Cloud Services Private Limited",
        vendor_gstin="29AABCA1234F1Z5", # Karnataka (29)
        vendor_address="Indiranagar 100ft Road, Bengaluru, Karnataka - 560038",
        customer_name="Sakshi Financial Systems",
        customer_gstin="36AAACH7409R1ZZ", # Telangana (36)
        customer_address="HITEC City, Madhapur, Hyderabad, Telangana - 500081",
        place_of_supply="36-Telangana",
        items=[
            {
                "desc": "Enterprise Cloud Server Infrastructure",
                "hsn": "998313",
                "qty": "1.0",
                "price": 100000.0,
                "taxable": 100000.0,
                "total": 118000.0
            }
        ],
        subtotal=100000.0,
        tax_type="IGST",
        tax_rate=18.0,
        total_amount=118000.0,
        output_path="scratch/invoice_interstate_29_to_36.png"
    )

    # 2. Generate Intra-State Invoice
    generate_sample_invoice_image(
        invoice_number="INV-2026-INTRA-002",
        invoice_date="2026-08-25",
        vendor_name="Telangana Tech Solvers LLP",
        vendor_gstin="36AABCU9603R1ZM", # Telangana (36)
        vendor_address="Gachibowli Financial District, Hyderabad, Telangana - 500032",
        customer_name="Sakshi Financial Systems",
        customer_gstin="36AAACH7409R1ZZ", # Telangana (36)
        customer_address="HITEC City, Madhapur, Hyderabad, Telangana - 500081",
        place_of_supply="36-Telangana",
        items=[
            {
                "desc": "IT Infrastructure Maintenance & Support",
                "hsn": "998314",
                "qty": "1.0",
                "price": 50000.0,
                "taxable": 50000.0,
                "total": 59000.0
            }
        ],
        subtotal=50000.0,
        tax_type="CGST_SGST",
        tax_rate=18.0,
        total_amount=59000.0,
        output_path="scratch/invoice_intrastate_36_to_36.png"
    )
