from app.contacts import extract_contacts, normalize_phone, listing_card


def test_phones_and_whatsapp():
    c = extract_contacts("דירה בחולון 5,200 ש״ח. לפרטים 050-123-4567 או 03-5551234, wa.me לא כאן. +972 52 765 4321")
    nums = [p["display"] for p in c["phones"]]
    assert "050-123-4567" in nums and "03-555-1234" in nums or "03-5551234" in nums or any(n.startswith("03") for n in nums)
    assert any(p["display"] == "052-765-4321" for p in c["phones"])
    mob = [p for p in c["phones"] if p["mobile"]][0]
    assert mob["whatsapp"].startswith("https://wa.me/972") and mob["tel"].startswith("+972")
    assert c["has_direct"] is True


def test_prices_are_not_phones():
    c = extract_contacts("דירת 3 חדרים בחולון 5,200 ש״ח, קומה 2, 85 מ״ר, 2024")
    assert c["phones"] == [] and c["has_direct"] is False


def test_links_email_source():
    c = extract_contacts("כתבו ל-Owner@Example.com או https://wa.me/972501234567 או t.me/x https://t.me/someone", "https://www.yad2.co.il/item/1")
    assert c["emails"] == ["owner@example.com"] and c["whatsapp_links"] == ["https://wa.me/972501234567"]
    assert c["telegram_links"] == ["https://t.me/someone"] and c["source"]["host"] == "yad2.co.il"
    assert extract_contacts("x", "javascript:alert(1)")["source"] is None


def test_normalize():
    assert normalize_phone("+972-50-123-4567") == "0501234567" and normalize_phone("12345") is None
