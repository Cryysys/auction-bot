class Auction:
    def __init__(
        self,
        channel,
        seller,
        item_name,
        start_price,
        min_increment,
        end_time,
        start_message,
        currency_symbol,
    ):
        self.channel = channel
        self.seller = seller
        self.item_name = item_name
        self.start_price = start_price
        self.min_increment = min_increment
        self.current_price = start_price
        self.end_time = end_time
        self.highest_bidder = None
        self.bidders = set()
        self.start_message = start_message
        self.currency_symbol = currency_symbol
        self.reminder_1h_sent = False
        self.reminder_5m_sent = False
        self.end_task = None
        self.reminder_task = None
        self.last_bid_message = None
        self.message = None  # To track the "Live Card"
        self.image_url = None  # To store the link to the art
