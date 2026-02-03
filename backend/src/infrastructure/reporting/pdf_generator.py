from pathlib import Path
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import logging

class PDFReportGenerator:
    """Generates professional PDF reports from CRM data."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._register_fonts()
        self.styles = self._create_styles()

    def _register_fonts(self):
        """Register fonts that support Turkish characters."""
        try:
            # Try to register LiberationSans (common in Linux/Docker)
            font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            bold_font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
            italic_font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf"
            
            if Path(font_path).exists():
                pdfmetrics.registerFont(TTFont('TurkishFont', font_path))
                pdfmetrics.registerFont(TTFont('TurkishFont-Bold', bold_font_path))
                pdfmetrics.registerFont(TTFont('TurkishFont-Italic', italic_font_path))
                self.font_name = 'TurkishFont'
                self.logger.info("Registered LiberationSans font for Turkish support.")
            else:
                self.logger.warning("LiberationSans not found. Falling back to Helvetica (Turkish chars may fail).")
                self.font_name = 'Helvetica' # Fallback
                
        except Exception as e:
            self.logger.error(f"Font registration failed: {e}")
            self.font_name = 'Helvetica'

    def _create_styles(self):
        """Create custom styles for the report."""
        styles = getSampleStyleSheet()
        
        # Title Style
        styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=styles['Heading1'],
            fontName=f'{self.font_name}-Bold' if self.font_name != 'Helvetica' else 'Helvetica-Bold',
            fontSize=24,
            textColor=colors.HexColor('#1a237e'), # Navy Blue
            spaceAfter=20,
            alignment=1 # Center
        ))
        
        # Section Header - More technical
        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading2'],
            fontName=f'{self.font_name}-Bold' if self.font_name != 'Helvetica' else 'Helvetica-Bold',
            fontSize=16,
            textColor=colors.HexColor('#1565c0'), # A bit lighter blue
            spaceBefore=20,
            spaceAfter=12,
            borderPadding=8,
            borderColor=colors.HexColor('#1565c0'),
            borderWidth=0,
            borderBottomWidth=1.5 # Thicker bottom line
        ))
        
        # Normal Text
        styles.add(ParagraphStyle(
            name='TurkishBody',
            parent=styles['Normal'],
            fontName=self.font_name,
            fontSize=11,
            leading=15, # More breathing room
            spaceAfter=8
        ))
        
        # Analysis Box Style - Full Box with better padding
        styles.add(ParagraphStyle(
            name='AnalysisBox',
            parent=styles['Normal'],
            fontName=self.font_name,
            fontSize=11,
            leading=16, # Increased leading for readability
            backColor=colors.HexColor('#f8f9fa'),
            borderColor=colors.HexColor('#e0e0e0'),
            borderWidth=1, # Restored full border
            borderPadding=15, # Increased padding to prevent text overlap
            spaceBefore=5, # Space between title and box
            spaceAfter=20
        ))
        
        # Bullet Point Style
        styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=styles['Normal'],
            fontName=self.font_name,
            fontSize=11,
            leading=15,
            leftIndent=15,
            spaceAfter=4,
            textColor=colors.HexColor('#424242')
        ))

        return styles

    def generate(self, report_data: dict, output_path: Path) -> str:
        """Generate the PDF report."""
        try:
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=50, leftMargin=50, # More whitespace
                topMargin=50, bottomMargin=50
            )
            
            story = []
            
            # 1. Header & Title
            story.append(Paragraph("Güllüoğlu İnşaat | AI Emlak Raporu", self.styles["ReportTitle"]))
            story.append(Paragraph(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}", 
                                 ParagraphStyle('Date', parent=self.styles["TurkishBody"], alignment=1, textColor=colors.grey)))
            story.append(Spacer(1, 25))
            
            # 2. Customer Profile
            story.append(Paragraph("1. Müşteri Profili", self.styles["SectionHeader"]))
            client_info = report_data.get("musteri_bilgileri", {})
            prof_info = report_data.get("profesyonel_bilgiler", {})
            family_info = report_data.get("aile_bilgileri", {})

            profile_data = [
                ["İsim Soyisim:", client_info.get("isim", "-")],
                ["İletişim:", f"{client_info.get('telefon', '-')} / {client_info.get('email', '-')}"],
                ["Memleket:", client_info.get("memleket", "-")],
                ["Yaşadığı Yer:", f"{client_info.get('yasadigi_sehir', '-')} / {client_info.get('yasadigi_ilce', '-')}"],
                ["Meslek:", prof_info.get("meslek", "-")],
                ["Tahmini Gelir:", prof_info.get("tahmini_maas", "-")],
                ["Medeni Durum:", family_info.get("medeni_durum", "-")],
                ["Aile Yapısı:", "Çocuk Var" if family_info.get("cocuk_var_mi") is True else ("Çocuk Yok" if family_info.get("cocuk_var_mi") is False else "Belirtilmedi")]
            ]
            
            self._add_table(story, profile_data)
            
            # 3. Requirements
            story.append(Paragraph("2. Konut Beklentileri", self.styles["SectionHeader"]))
            housing_prefs = report_data.get("konut_tercihleri", {})
            budget_info = report_data.get("butce_analizi", {})
            
            # Format social amenities list
            social_amenities = housing_prefs.get('sosyal_alanlar', [])
            if social_amenities and len(social_amenities) > 0:
                social_text = ", ".join(social_amenities)
            else:
                social_text = "Belirtilmedi"
            
            housing_data = [
                ["Hedef Lokasyon:", f"{housing_prefs.get('hedef_sehir', '-')} / {housing_prefs.get('hedef_ilce', '-')}"],
                ["Oda Sayısı:", str(housing_prefs.get('oda_sayisi', '-'))],
                ["Konut Tipi:", housing_prefs.get('ev_tipi', '-')],
                ["Satın Alma Amacı:", housing_prefs.get('satin_alma_amaci', '-')],
                ["Sosyal Alanlar:", social_text],
                ["Birikim Durumu:", housing_prefs.get('birikim_durumu', '-')],
                ["Kredi Kullanımı:", housing_prefs.get('kredi_kullanimi', '-')],
                ["Takas Tercihi:", housing_prefs.get('takas_tercihi', '-')],
                ["Bütçe Limiti:", f"{budget_info.get('belirtilen_butce', '-')} {budget_info.get('para_birimi', 'TRY')}"],
                ["Önerilen Segment:", budget_info.get('tavsiye_edilen_segment', '-')]
            ]
            
            self._add_table(story, housing_data)
            
            # 4. AI Strategic Analysis
            story.append(Paragraph("3. AI Stratejik Analizi", self.styles["SectionHeader"]))
            ai_eval = report_data.get("ai_degerlendirmesi", {})
            
            # Helper to clean text (remove existing numbering like "1.", "-", etc)
            import re
            def clean_text(text):
                if not text: return ""
                # Remove leading numbers, bullets, dashes (e.g., "1. ", "- ", "* ")
                return re.sub(r'^\s*(?:\d+[\.)]|\-|•|\*)\s*', '', str(text).strip())

            # 4.0 Detailed Analysis Paragraph
            detailed_analysis = ai_eval.get("detayli_analiz")
            if detailed_analysis:
                story.append(Paragraph("<b>📋 Detaylı Analiz:</b>", self.styles["TurkishBody"]))
                story.append(Paragraph(detailed_analysis, self.styles["AnalysisBox"]))
                
            # 4.1 Executive Summary
            summary = ai_eval.get("ozet")
            if summary:
                story.append(Paragraph("<b>📊 Genel Değerlendirme:</b>", self.styles["TurkishBody"]))
                story.append(Paragraph(summary, self.styles["AnalysisBox"]))
            
            # 4.2 Behavioral Metrics
            story.append(Paragraph("<b>🎯 Davranışsal Metrikler:</b>", self.styles["TurkishBody"]))
            metrics_data = [
                ["Risk İştahı:", ai_eval.get("risk_istahi", "-")],
                ["Satın Alma Motivasyonu:", ai_eval.get("satin_alma_motivasyonu", "-")],
                ["Satın Alma Zamanlaması:", ai_eval.get("satin_alma_zamani", "-")]
            ]
            self._add_table(story, metrics_data, col_widths=[140, 310]) # Adjusted widths
            story.append(Spacer(1, 15))
            
            # 4.3 Lifestyle Insights
            notes = ai_eval.get("yasam_tarzi_notlari", [])
            if notes:
                story.append(Paragraph("<b>🔍 Yaşam Tarzı Analizi (Sohbet Bağlamından):</b>", self.styles["TurkishBody"]))
                story.append(Paragraph("AI'ın sohbet sırasında tespit ettiği önemli noktalar:", self.styles["TurkishBody"]))
                for note in notes:
                    story.append(Paragraph(f"• {clean_text(note)}", self.styles["BulletPoint"]))
                story.append(Spacer(1, 15))
            
            # 4.4 Strategic Recommendations
            recs = ai_eval.get("tavsiyeler", [])
            if recs:
                story.append(Paragraph("<b>💡 Önerilen Stratejiler:</b>", self.styles["TurkishBody"]))
                for rec in recs:
                    story.append(Paragraph(f"• {clean_text(rec)}", self.styles["BulletPoint"]))
                story.append(Spacer(1, 15))
            
            # 4.5 Key Considerations
            considerations = ai_eval.get("dikkat_noktalari", [])
            if considerations:
                story.append(Paragraph("<b>⚠️ Dikkat Edilmesi Gereken Noktalar:</b>", self.styles["TurkishBody"]))
                for note in considerations:
                    story.append(Paragraph(f"• {clean_text(note)}", self.styles["BulletPoint"]))
                story.append(Spacer(1, 15))

            # 5. Footer
            story.append(Spacer(1, 40))
            disclaimer = "Bu rapor, yapay zeka tarafından kullanıcının beyanlarına dayanarak oluşturulmuştur. Kesin yatırım tavsiyesi değildir."
            story.append(Paragraph(disclaimer, ParagraphStyle('Disclaimer', parent=self.styles['Italic'], fontSize=9, textColor=colors.grey, alignment=1)))

            doc.build(story)
            self.logger.info(f"PDF Generated successfully: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Failed to generate PDF: {e}", exc_info=True)
            raise e

    def _add_table(self, story, data, col_widths=[130, 360]):
        """Helper to add styled table."""
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), self.font_name),
            # Key Column (First Col)
            ('FONTNAME', (0,0), (0,-1), f'{self.font_name}-Bold' if self.font_name != 'Helvetica' else 'Helvetica-Bold'),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1a237e')), # Navy Blue Keys
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            # Value Column (Second Col)
            ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#424242')),
            # Layout
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            # Dividers
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#eeeeee')), # Light horizontal lines
        ]))
        story.append(t)
        story.append(Spacer(1, 15))
