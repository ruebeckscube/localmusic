import io
from django.conf import settings
from django.urls import reverse
import segno
import fpdf

from django.contrib.staticfiles import finders


def _get_qr_svg(url):
    qrcode = segno.make(url, error='m')
    buf = io.BytesIO()
    qrcode.save(out=buf, kind='svg', scale=3, omitsize=True)
    return buf


def _write_line(pdf, text, size, align=fpdf.Align.C, padding=(.02, 0)):
    pdf.set_font('', size=size)
    pdf.multi_cell(text=text, w=0, align=align, new_x=fpdf.XPos.LMARGIN, new_y=fpdf.YPos.NEXT, padding=padding)


def _write_list_item(pdf, list_icon, text):
    y = pdf.get_y()
    pdf.set_x(pdf.l_margin + .2)
    pdf.image(list_icon, w=.3, h=.3)
    pdf.set_y(y)
    pdf.set_x(pdf.l_margin + .5)
    pdf.multi_cell(text=text, w=0, new_x=fpdf.XPos.LEFT, new_y=fpdf.YPos.NEXT, padding=(0,0,.1))


def generate_artist_qr_kit(pk, name):
    url = f"https://{settings.HOST_NAME}{reverse('findshows:follow_artist', args=(pk,))}"

    pdf = fpdf.FPDF('portrait', format=(8.5, 11), unit='in')
    pdf.add_page()
    pdf.add_font('LeagueMono', fname=finders.find('findshows/LeagueMono/LeagueMono.ttf'))
    pdf.set_font('LeagueMono')
    star_svg = finders.find('findshows/follow-star-filled.svg')

    pdf.ln(h=.5)
    _write_line(pdf, 'follow', 20)
    _write_line(pdf, name, 48)
    _write_line(pdf, 'on', 20)
    _write_line(pdf, settings.SITE_TITLE, 48)

    pdf.image(_get_qr_svg(url), x=fpdf.Align.C, w=4, h=4)

    _write_line(pdf, 'Sign up to:', 20, fpdf.Align.L, (0, 0, .1))
    _write_list_item(pdf, star_svg, 'get a weekly email with shows from bands you follow plus other recommended shows from local artists')
    _write_list_item(pdf, star_svg, 'browse shows on the site,  and listen ahead with embedded players')
    _write_list_item(pdf, star_svg, 'help free the local music scene from the evil clutches of instagram')

    return pdf.output()
