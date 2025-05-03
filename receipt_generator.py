from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os
import qrcode
from io import BytesIO

# Enregistrement des polices (à faire une seule fois dans votre application)
try:
    pdfmetrics.registerFont(TTFont('Roboto', 'Roboto-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Bold', 'Roboto-Bold.ttf'))
except:
    # Fallback aux polices standard si les polices personnalisées ne sont pas disponibles
    pass
def generate_receipt_pdf(transaction_data, client_data, iban_data, company_name, 
                        logo_path=None, receipt_title="REÇU DE TRANSACTION", 
                        additional_notes="", include_signature=True, include_qr=True):
                        
    """
    Génère un reçu PDF professionnel avec QR code
    
    Args:
        transaction_data: Données de la transaction
        client_data: Données du client
        iban_data: Données du compte
        company_name: Nom de l'entreprise
        logo_path: Chemin vers le logo
        receipt_title: Titre du document
        additional_notes: Notes additionnelles
        include_signature: Inclure une ligne de signature
        qr_code: Booléen pour inclure ou non le QR code
        include_signature: Inclure une ligne de signature
        include_qr: Inclure un QR code de vérification
    
    Returns:
        Chemin vers le fichier PDF généré
    """
    # Créer le dossier de sortie
    os.makedirs("receipts", exist_ok=True)
    pdf_path = f"receipts/receipt_{transaction_data['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # Créer le document avec des marges plus modernes
    doc = SimpleDocTemplate(
        pdf_path, 
        pagesize=A4,
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    # Styles personnalisés
    styles = getSampleStyleSheet()
    
    # Modifier les styles existants ou ajouter des nouveaux
    if 'Title' not in styles:
        styles.add(ParagraphStyle(
            name='Title',
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            alignment=1,  # Centré
            spaceAfter=12,
            textColor=colors.HexColor('#2c3e50')
        ))
    
    if 'Heading2' not in styles:
        styles.add(ParagraphStyle(
            name='Heading2',
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=15,
            spaceAfter=6,
            textColor=colors.HexColor('#3498db')
        ))
    
    # Modifier le style Normal existant
    styles['Normal'].fontName = 'Helvetica'
    styles['Normal'].textColor = colors.HexColor('#333333')
    
    # Éléments du PDF
    elements = []
    
    # En-tête avec logo
    if logo_path and os.path.exists(logo_path):
        logo = Image(logo_path, width=4*cm, height=2*cm)
        elements.append(logo)
        elements.append(Spacer(1, 0.5*cm))
    
    # Titre principal
    elements.append(Paragraph(receipt_title, styles['Title']))
    elements.append(Paragraph(company_name, styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Ligne de séparation
    elements.append(HRFlowable(
        width="100%",
        thickness=1,
        lineCap='round',
        color=colors.HexColor('#3498db'),
        spaceAfter=0.5*cm
    ))
    
    # Informations de la transaction
    trans_date = datetime.strptime(transaction_data['date'], '%Y-%m-%d %H:%M:%S')
    formatted_amount = f"{float(transaction_data['amount']):,.2f}".replace(",", " ")
    
    transaction_info = [
        ["Référence", transaction_data['id']],
        ["Date", trans_date.strftime('%d/%m/%Y %H:%M')],
        ["Type", transaction_data['type'].upper()],
        ["Montant", f"{formatted_amount} {iban_data['currency']}"],
        ["IBAN", iban_data['iban']],
        ["Description", transaction_data['description'] or "-"]
    ]
    
    t = Table(transaction_info, colWidths=[3*cm, 12*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#eeeeee'))
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 0.5*cm))
    
    # Informations client
    elements.append(Paragraph("INFORMATIONS CLIENT", styles['Heading4']))
    
    client_info = [
        ["Nom", f"{client_data['first_name']} {client_data['last_name']}"],
        ["Type", client_data['type']],
        ["Email", client_data['email'] or "-"],
        ["Téléphone", client_data['phone'] or "-"]
    ]
    
    t = Table(client_info, colWidths=[3*cm, 12*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#eeeeee'))
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 0.5*cm))

    # Ajoutez cette partie pour le QR code conditionnel
    if include_qr:
        qr_data = f"""
        TRANSACTION #{transaction_data['id']}
        Date: {trans_date.strftime('%d/%m/%Y %H:%M')}
        Client: {client_data['first_name']} {client_data['last_name']}
        IBAN: {iban_data['iban']}
        Montant: {formatted_amount} {iban_data['currency']}
        """
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        qr_img = Image(img_bytes, width=3*cm, height=3*cm)
        elements.append(Spacer(1, 0.5*cm))
        elements.append(qr_img)
        elements.append(Paragraph(
            "<i>Scannez ce code pour vérifier la transaction</i>",
            styles['Italic']
        ))

    
    # Notes additionnelles
    if additional_notes:
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph("NOTES", styles['Heading4']))
        elements.append(Paragraph(additional_notes.replace('\n', '<br/>'), styles['Normal']))
    
    # Signature
    if include_signature:
        elements.append(Spacer(1, 1*cm))
        signature_table = Table([
            ["", "Signature"],
            ["", "Pour " + company_name]
        ], colWidths=[10*cm, 5*cm])
        
        signature_table.setStyle(TableStyle([
            ('LINEABOVE', (1, 0), (1, 0), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#555555')),
            ('LEFTPADDING', (0, 0), (0, -1), 0),
            ('TOPPADDING', (1, 1), (1, 1), 0)
        ]))
        
        elements.append(signature_table)
    
    # Pied de page
    elements.append(Spacer(1, 1*cm))
    footer_text = f"""
    {company_name} • Reçu généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
    <br/>
    Ce document est une preuve officielle de transaction. Conservez-le précieusement.
    """
    
    elements.append(Paragraph(footer_text, ParagraphStyle(
        name='Footer',
        fontName='Helvetica',
        fontSize=8,
        leading=9,
        alignment=1,
        textColor=colors.HexColor('#7f8c8d')
    )))
    
    # Générer le PDF
    doc.build(elements)
    return pdf_path
