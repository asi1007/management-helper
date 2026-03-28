from infrastructure.amazon.merchant_listings_sku_resolver import MerchantListingsSkuResolver

class TestExtractAsinSkuMap:
    def test_parses_tsv_english_headers(self):
        tsv = "item-name\titem-description\tlisting-id\tseller-sku\tprice\tquantity\topen-date\timage-url\titem-is-marketplace\tproduct-id-type\tzsku\tproduct-id\tasin1\n"
        tsv += "Product1\tdesc\tLIST1\tSKU-001\t100\t10\t2024-01-01\t\tY\tASIN\t\tB001\tB001\n"
        tsv += "Product2\tdesc\tLIST2\tSKU-002\t200\t5\t2024-01-02\t\tY\tASIN\t\tB002\tB002\n"
        resolver = MerchantListingsSkuResolver(auth_token="dummy")
        result = resolver._extract_asin_sku_map(tsv, ["B001", "B002"])
        assert result == {"B001": "SKU-001", "B002": "SKU-002"}

    def test_parses_tsv_japanese_headers(self):
        tsv = "商品名\t商品説明\t出品ID\t出品者SKU\t価格\t数量\t出品日\t画像URL\tマーケットプレイス\t商品IDタイプ\tzSKU\t商品ID\tASIN1\n"
        tsv += "商品A\t説明\tLIST1\tSKU-JP-1\t100\t10\t2024-01-01\t\tY\tASIN\t\tB001\tB001\n"
        resolver = MerchantListingsSkuResolver(auth_token="dummy")
        result = resolver._extract_asin_sku_map(tsv, ["B001"])
        assert result == {"B001": "SKU-JP-1"}

    def test_filters_by_requested_asins(self):
        tsv = "item-name\titem-description\tlisting-id\tseller-sku\tprice\tquantity\topen-date\timage-url\titem-is-marketplace\tproduct-id-type\tzsku\tproduct-id\tasin1\n"
        tsv += "P1\td\tL1\tSKU-1\t100\t10\t2024-01-01\t\tY\tASIN\t\tB001\tB001\n"
        tsv += "P2\td\tL2\tSKU-2\t200\t5\t2024-01-02\t\tY\tASIN\t\tB002\tB002\n"
        resolver = MerchantListingsSkuResolver(auth_token="dummy")
        result = resolver._extract_asin_sku_map(tsv, ["B001"])
        assert result == {"B001": "SKU-1"}
        assert "B002" not in result
