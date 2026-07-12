from PIL import Image, ImageDraw


sizes = [16, 24, 32, 48, 64, 128, 256]
images = []
for size in sizes:
    img = Image.new("RGBA", (size, size), "#102A43")
    draw = ImageDraw.Draw(img)
    border = max(1, size // 22)
    pad = max(2, size // 11)
    radius = max(3, size // 7)
    # 深蓝应用底座 + 蓝色内层，和旧版绿色文件图标完全区分。
    draw.rounded_rectangle((border, border, size - border, size - border), radius=radius, fill="#102A43")
    draw.rounded_rectangle((pad, pad, size - pad, size - pad), radius=max(2, radius - border), fill="#1F5C8C")

    # 两条相向的转换箭头，橙色圆点强调“格式转换”。
    stroke = max(1, size // 13)
    left = size * 5 // 24
    right = size * 19 // 24
    top = size * 9 // 24
    bottom = size * 15 // 24
    mid = size // 2
    draw.line((left, top, right - size // 7, top), fill="#F7FAFC", width=stroke)
    draw.line((right - size // 7, top, right - size // 7, mid - size // 10), fill="#F7FAFC", width=stroke)
    draw.polygon([(right - size // 7, mid - size // 10), (right, mid), (right - size // 7, mid + size // 10)], fill="#F7FAFC")
    draw.line((right, bottom, left + size // 7, bottom), fill="#F7FAFC", width=stroke)
    draw.line((left + size // 7, bottom, left + size // 7, mid + size // 10), fill="#F7FAFC", width=stroke)
    draw.polygon([(left + size // 7, mid + size // 10), (left, mid), (left + size // 7, mid - size // 10)], fill="#F7FAFC")
    dot = max(2, size // 10)
    draw.ellipse((mid - dot, mid - dot, mid + dot, mid + dot), fill="#FFB454")
    images.append(img)

images[-1].save("assets/format-converter.ico", format="ICO", sizes=[(s, s) for s in sizes])
