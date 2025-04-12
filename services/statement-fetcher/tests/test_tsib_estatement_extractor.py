# ruff: noqa: RUF001, W291

import os

from finchie_statement_fetcher.document_extractors.tsib_estatement_extractor import (
    RawCardTransactions,
    _extract_bill_info,
    _extract_transactions,
    _process_multiple_description,
    extract_credit_card_statement,
)


def test_extract_bill_info():
    """Test _extract_bill_info extracts bill information correctly"""
    # Read test data
    test_data_path = os.path.join(os.path.dirname(__file__), "test_data", "TSB_Creditcard_Estatement_202502.pdf.txt")
    with open(test_data_path, encoding="utf-8") as f:
        test_data = f.read()

    bill_info = _extract_bill_info(test_data)

    # Test if key items are extracted correctly
    assert bill_info["帳單結帳日"] == "114/02/07"
    assert bill_info["繳款截止日"] == "114/02/24"
    assert bill_info["上期應繳總額"] == "11,111"
    assert bill_info["已繳退款總額"] == "11,111"
    assert bill_info["前期餘額"] == "0"
    assert bill_info["本期新增款項"] == "22,222"
    assert bill_info["本期累計應繳金額"] == "22,222"
    assert bill_info["本期最低應繳金額"] == "3,333"
    assert bill_info["信用額度"] == "444,444"
    assert bill_info["國內預借現金額"] == "55,555"
    assert bill_info["國外預借現金額度"] == "66,666"
    assert bill_info["分期吉時金額度"] == "77,777"
    assert bill_info["循環信用利率"] == "6.75"


def test_extract_transactions():
    """Test _extract_transactions extracts transactions correctly"""
    # Prepare test data with transaction details
    test_data = """
        消費日 入帳起息日消費明細 新臺幣金額 外幣折算日 消費地 幣別 外幣金額
        台新銀行帳戶自動轉帳扣繳台新信用
        114/01/22 114/01/22 -11,111
        卡款
        信用卡A 姓名1 (卡號末四碼:1111)
        114/01/15 114/01/16 MOMO 1000
        114/01/20 114/01/21 UBER EATS 500
        114/01/25 114/01/26 KLOOK 3000 25 US USD 100.00
        CreditCardB 姓名2 (卡號末四碼:2222)
        114/01/10 114/01/11 全家便利商店 100
        """

    transactions = _extract_transactions(test_data)

    # Check if two cards are extracted correctly
    assert len(transactions) == 3  # Including the empty initial card and two actual cards

    # Check information of the first card
    gogo_card = transactions[1]
    assert gogo_card.card_name == "信用卡A"
    assert gogo_card.card_holder_name == "姓名1"
    assert gogo_card.card_last_four == "1111"
    assert len(gogo_card.transactions) == 3

    # Check transactions of the first card
    assert gogo_card.transactions[0].transaction_date == "114/01/15"
    assert gogo_card.transactions[0].posting_date == "114/01/16"
    assert gogo_card.transactions[0].description == "MOMO"
    assert gogo_card.transactions[0].new_taiwan_dollar_amount == "1000"

    # Check foreign currency transactions
    assert gogo_card.transactions[2].transaction_date == "114/01/25"
    assert gogo_card.transactions[2].posting_date == "114/01/26"
    assert gogo_card.transactions[2].description == "KLOOK"
    assert gogo_card.transactions[2].new_taiwan_dollar_amount == "3000"
    assert gogo_card.transactions[2].foreign_currency_date == "25"
    assert gogo_card.transactions[2].location == "US"
    assert gogo_card.transactions[2].currency == "USD"
    assert gogo_card.transactions[2].foreign_currency_amount == "100.00"

    # Check the second card
    rose_card = transactions[2]
    assert rose_card.card_name == "CreditCardB"
    assert rose_card.card_holder_name == "姓名2"
    assert rose_card.card_last_four == "2222"
    assert len(rose_card.transactions) == 1


def test_process_multiple_description_with_missing_description():
    """Test _process_multiple_description handles missing description"""
    description = ""
    none_processed_lines = ["previous line description"]
    lines = ["next line description"]
    current_index = 0

    result_description, result_index = _process_multiple_description(description, none_processed_lines, lines, current_index)

    assert result_description == "previous line descriptionnext line description"
    assert result_index == 1
    assert none_processed_lines == []


def test_process_multiple_description_with_description():
    """Test _process_multiple_description when description is already present"""
    description = "existing description"
    none_processed_lines = ["other line"]
    lines = ["other line"]
    current_index = 0

    result_description, result_index = _process_multiple_description(description, none_processed_lines, lines, current_index)

    assert result_description == "existing description"
    assert result_index == 0
    assert none_processed_lines == ["other line"]


def test_process_multiple_description_with_empty_lists():
    """Test _process_multiple_description with empty lists returns None"""
    description = ""
    none_processed_lines = []
    lines = []
    current_index = 0

    result_description, result_index = _process_multiple_description(description, none_processed_lines, lines, current_index)

    assert result_description is None
    assert result_index == 0


def test_extract_credit_card_statement(mocker):
    """Test extract_credit_card_statement extracts data from PDF correctly"""

    _mock_pdf(mocker)

    # Call the function being tested
    mock_extract_bill = mocker.patch("finchie_statement_fetcher.document_extractors.tsib_estatement_extractor._extract_bill_info")
    mock_extract_transactions = mocker.patch("finchie_statement_fetcher.document_extractors.tsib_estatement_extractor._extract_transactions")

    mock_bill_info = {"帳單結帳日": "114/02/07"}
    mock_transactions = [RawCardTransactions()]

    mock_extract_bill.return_value = mock_bill_info
    mock_extract_transactions.return_value = mock_transactions

    result = extract_credit_card_statement("fake_path.pdf", "password")

    assert result.bill_info == mock_bill_info
    assert result.transactions == mock_transactions

    # Use mocker.ANY to ignore exact parameter content matching
    mock_extract_bill.assert_called_once_with(mocker.ANY)
    mock_extract_transactions.assert_called_once_with(mocker.ANY)


def test_extract_credit_card_statement_error(mocker):
    """Test extract_credit_card_statement handles errors correctly"""
    # Simulate error when opening PDF
    mocker.patch("pdfplumber.open", side_effect=Exception("PDF Error"))

    result = extract_credit_card_statement("fake_path.pdf", "password")

    assert result is None


def _mock_pdf(mocker, file_path="TSB_Creditcard_Estatement_202502.pdf.txt", gogo_statement="", rose_statement=""):
    """Mock the pdfplumber.open method to return a mock PDF object."""
    # Read test data
    test_data_path = os.path.join(os.path.dirname(__file__), "test_data", file_path)
    with open(test_data_path, encoding="utf-8") as f:
        test_data = f.read()

    test_data = test_data.replace("{{ GoGoStatement }}", gogo_statement)
    test_data = test_data.replace("{{ RoseGivingStatement }}", rose_statement)

    # Setup mock to return test data
    mock_page = mocker.MagicMock()
    mock_page.extract_text.return_value = test_data

    mock_pdf = mocker.MagicMock()
    mock_pdf.pages = [mock_page]

    # Setup mock for opening PDF
    mock_pdf_open = mocker.patch("pdfplumber.open")
    mock_pdf_open.return_value.__enter__.return_value = mock_pdf


def test_extract_credit_card_statement_with_special_formats(mocker):
    """Test extract_credit_card_statement handles special format transactions correctly"""
    # Prepare special format transaction data
    gogo_statement = """
        114/02/15 114/02/18 ＷｏｒｌｄＧｙTAICHU 1,111 TW
        ｆｏｏｄｐａｎｄａ－ＬＩＮＥ
        114/03/07 114/03/12 2,222 TW
        Taipei
        114/04/20 114/04/22 GOOGLE*YOUTUBEPREMIUMG.CO/H 3,333 US
    """

    rose_statement = """
        114/05/28 114/06/05 TAOBAO.COMA2705 125 LO 2,000 GB
    """

    # Mock PDF with special format transaction data
    _mock_pdf(mocker, gogo_statement=gogo_statement, rose_statement=rose_statement)

    # Call the function being tested
    result = extract_credit_card_statement("fake_path.pdf", "password")

    # Verify the result
    assert result is not None

    # Find the cards with transactions
    gogo_card = None
    rose_card = None
    for card in result.transactions:
        if card.card_name == "@GoGo虛擬御璽卡":
            gogo_card = card
        elif card.card_name == "玫瑰Giving悠遊商務御璽卡":
            rose_card = card

    # Check if GoGo card transactions are parsed correctly
    assert gogo_card is not None
    assert len(gogo_card.transactions) == 3

    # Check full-width characters transaction
    assert gogo_card.transactions[0].transaction_date == "114/02/15"
    assert gogo_card.transactions[0].posting_date == "114/02/18"
    assert gogo_card.transactions[0].description == "ＷｏｒｌｄＧｙTAICHU"
    assert gogo_card.transactions[0].new_taiwan_dollar_amount == "1,111"
    assert gogo_card.transactions[0].location == "TW"

    # Check multi-line description transaction
    assert gogo_card.transactions[1].transaction_date == "114/03/07"
    assert gogo_card.transactions[1].posting_date == "114/03/12"
    assert gogo_card.transactions[1].description == "ｆｏｏｄｐａｎｄａ－ＬＩＮＥTaipei"
    assert gogo_card.transactions[1].new_taiwan_dollar_amount == "2,222"
    assert gogo_card.transactions[1].location == "TW"

    # Check transaction with special characters
    assert gogo_card.transactions[2].transaction_date == "114/04/20"
    assert gogo_card.transactions[2].posting_date == "114/04/22"
    assert gogo_card.transactions[2].description == "GOOGLE*YOUTUBEPREMIUMG.CO/H"
    assert gogo_card.transactions[2].new_taiwan_dollar_amount == "3,333"
    assert gogo_card.transactions[2].location == "US"

    # Check Rose card transaction with number+uppercase letters after description
    assert rose_card is not None
    assert len(rose_card.transactions) == 1
    assert rose_card.transactions[0].transaction_date == "114/05/28"
    assert rose_card.transactions[0].posting_date == "114/06/05"
    assert rose_card.transactions[0].description == "TAOBAO.COMA2705 125 LO"
    assert rose_card.transactions[0].new_taiwan_dollar_amount == "2,000"
    assert rose_card.transactions[0].location == "GB"


def test_extract_credit_card_statement_with_complex_formats(mocker):
    """Test extract_credit_card_statement handles more complex transaction formats"""
    # Prepare complex format transaction data
    gogo_statement = """
        114/01/15 114/01/20 電商購物APP-123 1,088 
        健身俱樂部
        114/01/07 114/01/10 254 TW
        -年費
        114/01/20 114/01/22 NETFLIX.COM 399 US
    """

    rose_statement = """
        114/01/28 114/02/05 外送平台$50OFF 899 TW
        114/01/30 114/02/02 海外購物網$USD30 899 20 US USD 30.00
    """

    # Mock PDF with complex transaction data
    _mock_pdf(mocker, gogo_statement=gogo_statement, rose_statement=rose_statement)

    # Call the function being tested
    result = extract_credit_card_statement("fake_path.pdf", "password")

    # Verify the result
    assert result is not None

    # Find the cards with transactions
    gogo_card = None
    rose_card = None
    for card in result.transactions:
        if card.card_name == "@GoGo虛擬御璽卡":
            gogo_card = card
        elif card.card_name == "玫瑰Giving悠遊商務御璽卡":
            rose_card = card

    # Check if GoGo card transactions are parsed correctly
    assert gogo_card is not None
    assert len(gogo_card.transactions) == 3

    # Check transaction with hyphen and numbers
    assert gogo_card.transactions[0].transaction_date == "114/01/15"
    assert gogo_card.transactions[0].posting_date == "114/01/20"
    assert gogo_card.transactions[0].description == "電商購物APP-123"
    assert gogo_card.transactions[0].new_taiwan_dollar_amount == "1,088"

    # Check multi-line Chinese description
    assert gogo_card.transactions[1].transaction_date == "114/01/07"
    assert gogo_card.transactions[1].posting_date == "114/01/10"
    assert gogo_card.transactions[1].description == "健身俱樂部-年費"
    assert gogo_card.transactions[1].new_taiwan_dollar_amount == "254"
    assert gogo_card.transactions[1].location == "TW"

    # Check well-known service transaction
    assert gogo_card.transactions[2].transaction_date == "114/01/20"
    assert gogo_card.transactions[2].posting_date == "114/01/22"
    assert gogo_card.transactions[2].description == "NETFLIX.COM"
    assert gogo_card.transactions[2].new_taiwan_dollar_amount == "399"
    assert gogo_card.transactions[2].location == "US"

    # Check Rose card transaction with special characters and discount information
    assert rose_card is not None
    assert len(rose_card.transactions) == 2
    assert rose_card.transactions[0].transaction_date == "114/01/28"
    assert rose_card.transactions[0].posting_date == "114/02/05"
    assert rose_card.transactions[0].description == "外送平台$50OFF"
    assert rose_card.transactions[0].new_taiwan_dollar_amount == "899"
    assert rose_card.transactions[0].location == "TW"

    # Check foreign currency transaction with dollar sign
    assert rose_card.transactions[1].transaction_date == "114/01/30"
    assert rose_card.transactions[1].posting_date == "114/02/02"
    assert rose_card.transactions[1].description == "海外購物網$USD30"
    assert rose_card.transactions[1].new_taiwan_dollar_amount == "899"
    assert rose_card.transactions[1].foreign_currency_date == "20"
    assert rose_card.transactions[1].location == "US"
    assert rose_card.transactions[1].currency == "USD"
    assert rose_card.transactions[1].foreign_currency_amount == "30.00"


def test_extract_credit_card_statement_with_edge_cases(mocker):
    """Test extract_credit_card_statement handles edge cases and obfuscated data"""
    # Prepare edge case transaction data with real shop names
    gogo_statement = """
        114/03/15 114/03/20 OnlineShop 1,111 
        114/04/07 114/04/10 FoodPanda 2,222 TW
        114/05/20 114/05/22 GoogleServices 3,333 US
        114/06/25 114/06/28 7-ELEVEN 5,000
    """

    rose_statement = """
        114/07/28 114/08/05 TAOBAO.COM 10,000 GB
        114/09/30 114/10/02 AMAZON.CO.JP 20,000 25 JP JPY 100,000.00
        114/11/01 114/11/03 ShopeeSubscription 1,111
    """

    # Mock PDF with edge case transaction data
    _mock_pdf(mocker, gogo_statement=gogo_statement, rose_statement=rose_statement)

    # Call the function being tested
    result = extract_credit_card_statement("fake_path.pdf", "password")

    # Verify the result
    assert result is not None

    # Find the cards with transactions
    gogo_card = None
    rose_card = None
    for card in result.transactions:
        if card.card_name == "@GoGo虛擬御璽卡":
            gogo_card = card
        elif card.card_name == "玫瑰Giving悠遊商務御璽卡":
            rose_card = card

    # Check if GoGo card transactions are parsed correctly
    assert gogo_card is not None
    assert len(gogo_card.transactions) == 4

    # Check shop transaction
    assert gogo_card.transactions[0].transaction_date == "114/03/15"
    assert gogo_card.transactions[0].posting_date == "114/03/20"
    assert gogo_card.transactions[0].description == "OnlineShop"
    assert gogo_card.transactions[0].new_taiwan_dollar_amount == "1,111"

    # Check food delivery vendor
    assert gogo_card.transactions[1].transaction_date == "114/04/07"
    assert gogo_card.transactions[1].posting_date == "114/04/10"
    assert gogo_card.transactions[1].description == "FoodPanda"
    assert gogo_card.transactions[1].new_taiwan_dollar_amount == "2,222"
    assert gogo_card.transactions[1].location == "TW"

    # Check service subscription
    assert gogo_card.transactions[2].transaction_date == "114/05/20"
    assert gogo_card.transactions[2].posting_date == "114/05/22"
    assert gogo_card.transactions[2].description == "GoogleServices"
    assert gogo_card.transactions[2].new_taiwan_dollar_amount == "3,333"
    assert gogo_card.transactions[2].location == "US"

    # Check convenience store transaction
    assert gogo_card.transactions[3].transaction_date == "114/06/25"
    assert gogo_card.transactions[3].posting_date == "114/06/28"
    assert gogo_card.transactions[3].description == "7-ELEVEN"
    assert gogo_card.transactions[3].new_taiwan_dollar_amount == "5,000"

    # Check Rose card transactions
    assert rose_card is not None
    assert len(rose_card.transactions) == 3

    # Check online shopping platform
    assert rose_card.transactions[0].transaction_date == "114/07/28"
    assert rose_card.transactions[0].posting_date == "114/08/05"
    assert rose_card.transactions[0].description == "TAOBAO.COM"
    assert rose_card.transactions[0].new_taiwan_dollar_amount == "10,000"
    assert rose_card.transactions[0].location == "GB"

    # Check Japanese yen transaction
    assert rose_card.transactions[1].transaction_date == "114/09/30"
    assert rose_card.transactions[1].posting_date == "114/10/02"
    assert rose_card.transactions[1].description == "AMAZON.CO.JP"
    assert rose_card.transactions[1].new_taiwan_dollar_amount == "20,000"
    assert rose_card.transactions[1].foreign_currency_date == "25"
    assert rose_card.transactions[1].location == "JP"
    assert rose_card.transactions[1].currency == "JPY"
    assert rose_card.transactions[1].foreign_currency_amount == "100,000.00"

    # Check auto-renewal subscription transaction
    assert rose_card.transactions[2].transaction_date == "114/11/01"
    assert rose_card.transactions[2].posting_date == "114/11/03"
    assert rose_card.transactions[2].description == "ShopeeSubscription"
    assert rose_card.transactions[2].new_taiwan_dollar_amount == "1,111"


def test_extract_credit_card_statement_with_mixed_formats(mocker):
    """Test extract_credit_card_statement handles mixed transaction format data"""
    # Prepare mixed format transaction data
    mixed_statement = """
        114/01/28 114/02/05 ＷｏｒｌｄＧｙTAICHU 1,088 TW
        ｆｏｏｄｐａｎｄａ－ＬＩＮＥ
        114/01/07 114/01/10 254 TW
        Taipei
        114/01/20 114/01/22 TAOBAO.COMA2705 125 LO 1,099 GB
        114/01/15 114/01/20 電商購物APP-123 1,088 
        台灣大車隊計程車
        114/01/30 114/02/02 海外購物網$USD30 899 20 US USD 30.00
        114/01/15 114/01/20 Online Shop-***** 1,088 
        114/01/07 114/01/10 F**dP**da 254 TW
        114/01/25 114/01/28 超商-7-11 50
        114/01/30 114/02/02 AMAZON.CO.JP 3,699 25 JP JPY 15,000.00
    """

    # Mock PDF with mixed format transaction data
    _mock_pdf(mocker, gogo_statement=mixed_statement, rose_statement="")

    # Call the function being tested
    result = extract_credit_card_statement("fake_path.pdf", "password")

    # Verify the result
    assert result is not None

    # Find the GoGo card with transactions
    gogo_card = None
    for card in result.transactions:
        if card.card_name == "@GoGo虛擬御璽卡":
            gogo_card = card
            break

    # Check if transactions are parsed correctly from mixed format data
    assert gogo_card is not None
    assert len(gogo_card.transactions) >= 8  # We should have at least 8 transactions

    # Sample a few key transactions to verify correct parsing

    # Check full-width characters and multi-line descriptions
    found_fullwidth = False
    found_taobao = False
    found_amazon = False
    found_convenience = False

    for tx in gogo_card.transactions:
        if tx.description == "ＷｏｒｌｄＧｙTAICHU" and tx.new_taiwan_dollar_amount == "1,088":
            found_fullwidth = True
        elif "TAOBAO.COMA2705" in tx.description and tx.new_taiwan_dollar_amount == "1,099":
            found_taobao = True
        elif tx.description == "AMAZON.CO.JP" and tx.currency == "JPY":
            found_amazon = True
        elif tx.description == "超商-7-11" and tx.new_taiwan_dollar_amount == "50":
            found_convenience = True

    assert found_fullwidth, "Full-width character transaction not found"
    assert found_taobao, "TAOBAO transaction with special format not found"
    assert found_amazon, "Japanese yen transaction not found"
    assert found_convenience, "Convenience store transaction not found"


def test_extract_credit_card_statement_specific_cases(mocker):
    """Test extract_credit_card_statement with specific problematic cases as requested"""
    # Prepare transaction data with specific problematic formats
    gogo_statement = """
        114/08/15 114/08/20 ＷｏｒｌｄＧｙTAICHU 2,222 TW
        ｆｏｏｄｐａｎｄａ－ＬＩＮＥ
        114/09/07 114/09/10 3,333 TW
        Taipei
        114/10/20 114/10/22 GOOGLE*YOUTUBEPREMIUMG.CO/H 1,111 US
    """

    rose_statement = """
        114/11/28 114/12/05 TAOBAO.COMA2705 125 LO 5,555 GB
    """

    # Call the function being tested with real merchant names
    _mock_pdf(mocker, gogo_statement=gogo_statement, rose_statement=rose_statement)
    result = extract_credit_card_statement("fake_path.pdf", "password")

    # Verify the result
    assert result is not None

    # Find the cards with transactions
    gogo_card = None
    rose_card = None
    for card in result.transactions:
        if card.card_name == "@GoGo虛擬御璽卡":
            gogo_card = card
        elif card.card_name == "玫瑰Giving悠遊商務御璽卡":
            rose_card = card

    # Check if transactions are parsed correctly
    assert gogo_card is not None
    assert len(gogo_card.transactions) == 3

    # Verify full-width characters transaction
    assert gogo_card.transactions[0].transaction_date == "114/08/15"
    assert gogo_card.transactions[0].posting_date == "114/08/20"
    assert gogo_card.transactions[0].description == "ＷｏｒｌｄＧｙTAICHU"
    assert gogo_card.transactions[0].new_taiwan_dollar_amount == "2,222"
    assert gogo_card.transactions[0].location == "TW"

    # Verify multi-line description
    assert gogo_card.transactions[1].transaction_date == "114/09/07"
    assert gogo_card.transactions[1].posting_date == "114/09/10"
    assert gogo_card.transactions[1].description == "ｆｏｏｄｐａｎｄａ－ＬＩＮＥTaipei"
    assert gogo_card.transactions[1].new_taiwan_dollar_amount == "3,333"
    assert gogo_card.transactions[1].location == "TW"

    # Verify special character transaction
    assert gogo_card.transactions[2].transaction_date == "114/10/20"
    assert gogo_card.transactions[2].posting_date == "114/10/22"
    assert gogo_card.transactions[2].description == "GOOGLE*YOUTUBEPREMIUMG.CO/H"
    assert gogo_card.transactions[2].new_taiwan_dollar_amount == "1,111"
    assert gogo_card.transactions[2].location == "US"

    # Verify transaction with special format (number+uppercase after description)
    assert rose_card is not None
    assert len(rose_card.transactions) == 1
    assert rose_card.transactions[0].transaction_date == "114/11/28"
    assert rose_card.transactions[0].posting_date == "114/12/05"
    assert rose_card.transactions[0].description == "TAOBAO.COMA2705 125 LO"
    assert rose_card.transactions[0].new_taiwan_dollar_amount == "5,555"
    assert rose_card.transactions[0].location == "GB"
