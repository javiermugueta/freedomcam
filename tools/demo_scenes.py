"""Made-up scenes (no real photos) for the app's demo mode and the guide screenshots."""
import io

from PIL import Image, ImageDraw, ImageFilter

W, H = 1280, 720


def escena(tipo, hora, rnd, objetos):
    noche = hora < 7 or hora >= 19
    cielo = (40, 46, 60) if noche else (150, 190, 230)
    suelo = (60, 66, 60) if noche else (110, 150, 90)
    img = Image.new("RGB", (W, H), cielo)
    d = ImageDraw.Draw(img)
    horizonte = 330 if tipo != "hall" else 0
    if tipo == "hall":
        d.rectangle((0, 0, W, H), fill=(205, 196, 180) if not noche else (90, 86, 80))
        d.rectangle((0, 520, W, H), fill=(150, 110, 80) if not noche else (70, 55, 45))
        d.rectangle((520, 120, 760, 520), fill=(120, 80, 50))            # puerta
        d.ellipse((725, 320, 740, 335), fill=(220, 190, 90))
        d.rectangle((140, 160, 360, 330), fill=(170, 200, 220))          # cuadro / ventana
    else:
        d.rectangle((0, horizonte, W, H), fill=suelo)
        for i in range(6):                                               # árboles
            x = 60 + i * 230 + rnd.randint(-30, 30)
            d.rectangle((x + 30, horizonte - 40, x + 45, horizonte + 30), fill=(90, 60, 40))
            d.ellipse((x - 20, horizonte - 160, x + 95, horizonte - 20), fill=(50, 110, 60) if not noche else (30, 50, 35))
        if tipo == "driveway":
            d.polygon([(450, H), (830, H), (700, horizonte), (580, horizonte)], fill=(120, 120, 125) if not noche else (55, 55, 60))
            d.rectangle((880, 150, 1240, 360), fill=(220, 210, 190) if not noche else (80, 78, 72))  # casa
            d.polygon([(860, 150), (1060, 60), (1260, 150)], fill=(170, 80, 60))
            d.rectangle((1000, 250, 1080, 360), fill=(110, 70, 50))
    for o in objetos:
        x = rnd.randint(200, 900)
        if o == "car":
            y = rnd.randint(430, 560)
            color = rnd.choice([(200, 40, 40), (40, 80, 180), (230, 230, 230), (30, 30, 30)])
            d.rounded_rectangle((x, y, x + 300, y + 90), radius=25, fill=color)
            d.rounded_rectangle((x + 60, y - 55, x + 230, y + 10), radius=20, fill=color)
            d.rectangle((x + 80, y - 45, x + 210, y), fill=(170, 200, 220))
            for cx in (x + 60, x + 240):
                d.ellipse((cx - 32, y + 60, cx + 32, y + 124), fill=(20, 20, 20))
        elif o == "person":
            y = rnd.randint(360, 470) if tipo != "hall" else 300
            ropa = rnd.choice([(60, 70, 140), (150, 50, 50), (60, 120, 70)])
            d.ellipse((x, y, x + 50, y + 50), fill=(225, 185, 150))
            d.rounded_rectangle((x - 10, y + 55, x + 60, y + 170), radius=18, fill=ropa)
            d.rectangle((x + 2, y + 170, x + 22, y + 250), fill=(40, 40, 60))
            d.rectangle((x + 28, y + 170, x + 48, y + 250), fill=(40, 40, 60))
        elif o == "dog":
            y = rnd.randint(520, 600)
            d.ellipse((x, y, x + 120, y + 60), fill=(150, 100, 50))
            d.ellipse((x + 95, y - 30, x + 150, y + 20), fill=(150, 100, 50))
            for lx in (x + 15, x + 85):
                d.rectangle((lx, y + 45, lx + 12, y + 90), fill=(120, 80, 40))
    if noche:
        img = Image.blend(img.convert("L").convert("RGB"), img, 0.15)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=82)
    return out.getvalue()
