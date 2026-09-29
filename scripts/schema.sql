create table Users(
    email_pk VARCHAR(255) PRIMARY KEY ,
    password TEXT
);

create table HelpDesk(
    email_pk VARCHAR(255) PRIMARY KEY ,
    position TEXT
);

create table Requests(
    request_id_pk INTEGER PRIMARY KEY ,
    sender_email_fk VARCHAR(255),
    helpdesk_staff_email_fk VARCHAR(255),
    request_type TEXT,
    request_desc TEXT,
    request_status INTEGER,
    FOREIGN KEY (sender_email_fk) REFERENCES Users(email_PK),
    FOREIGN KEY (helpdesk_staff_email_fk) REFERENCES HelpDesk(email_PK)
);

CREATE TABLE Bidders(
    email_fk VARCHAR(255) PRIMARY KEY ,
    first_name TEXT,
    last_name TEXT,
    age INTEGER,
    home_address_id_fk TEXT,
    major TEXT,
    FOREIGN KEY (email_fk) REFERENCES Users(email_PK),
    FOREIGN KEY (home_address_id_fk) REFERENCES Address(address_ID_pk)
);

CREATE TABLE Credit_Cards(
    credit_card_num TEXT,
    card_type TEXT,
    expire_month INTEGER CHECK (expire_month>=1 AND expire_month<=12 ),
    expire_year INTEGER CHECK ( expire_year >= 1000 AND expire_year <= 9999),
    security_code INTEGER,
    owner_email_fk VARCHAR(255),
    PRIMARY KEY (owner_email_fk, credit_card_num), --weak entity
    FOREIGN KEY (owner_email_fk) REFERENCES Users(email_PK)
);

CREATE TABLE Address(
    address_ID_pk TEXT PRIMARY KEY ,
    zipcode_fk INTEGER,
    street_num INTEGER,
    street_name TEXT,
    FOREIGN KEY (zipcode_fk) REFERENCES Zipcode_Info(zipcode_pk)
);

CREATE TABLE Zipcode_Info(
    zipcode_pk INTEGER PRIMARY KEY,
    city TEXT,
    State TEXT
);

CREATE TABLE Sellers(
    email_fk VARCHAR(255) PRIMARY KEY ,
    bank_routing_number TEXT,
    bank_account_number INTEGER,
    balance INTEGER,
    FOREIGN KEY (email_fk) REFERENCES Users(email_PK)
);

CREATE TABLE Local_Vendors(
  email_fk varchar(255),
  business_name TEXT,
  business_address_ID_fk TEXT,
  customer_service_phone_number TEXT,
  FOREIGN KEY (email_fk) references Sellers(email_fk),
  FOREIGN KEY (business_address_ID_fk) references Address(address_ID_pk)
);

CREATE TABLE Categories( --parent child relationship
    parent_category_fk TEXT,
    category_name TEXT PRIMARY KEY,
    FOREIGN KEY (parent_category_fk) references Categories(category_name)
);

CREATE TABLE Auction_Listings(
    seller_email_fk varchar(255),
    listing_ID INTEGER,
    category_fk TEXT,
    auction_title TEXT,
    product_name TEXT,
    product_description TEXT,
    quantity INTEGER,
    reserve_price INTEGER,
    max_bids INTEGER,
    status INTEGER,
    PRIMARY KEY (seller_email_fk,listing_ID),
    FOREIGN KEY (seller_email_fk) REFERENCES Sellers(email_fk),
    FOREIGN KEY (category_fk) REFERENCES Categories(category_name)
);

CREATE TABLE Bids(
    Bid_ID INTEGER AUTO_INCREMENT,
    seller_email_fk VARCHAR(255),
    listing_ID_fk INTEGER,
    bidder_email_fk VARCHAR(255),
    bid_price INTEGER,
    PRIMARY KEY (Bid_ID),
    FOREIGN KEY (bidder_email_fk) REFERENCES Bidders(email_fk),
    FOREIGN KEY (seller_email_fk,listing_ID_fk) REFERENCES Auction_Listings(seller_email_fk,listing_ID)
);

CREATE TABLE Transactions(
    transaction_ID INTEGER AUTO_INCREMENT  ,
    seller_email_fk VARCHAR(255),
    listing_ID_fk INTEGER,
    buyer_email_fk varchar(255),
    date TEXT,
    payment INTEGER,
    PRIMARY KEY (transaction_ID),
    FOREIGN KEY (buyer_email_fk) REFERENCES Bidders(email_fk),
    FOREIGN KEY (seller_email_fk,listing_ID_fk) REFERENCES Auction_Listings(seller_email_fk,listing_ID)
);

CREATE TABLE Ratings(
    bidder_email_fk varchar(255),
    seller_email_fk varchar(255),
    date TEXT,
    rating INTEGER CHECK(rating>=1 AND rating <=5),
    rating_desc TEXT,
    PRIMARY KEY (bidder_email_fk,seller_email_fk,date),
    FOREIGN KEY (bidder_email_fk) references Bidders(email_fk),
    FOREIGN KEY (seller_email_fk) references  Sellers(email_fk)
);

CREATE TABLE Notifications(
    notification_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email_fk TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_email_fk) REFERENCES Users(email_pk)
);

CREATE TABLE ShoppingCart(
  bidder_email_fk varchar(255),
  seller_email_fk varchar(255),
  listing_ID_fk INTEGER,
  title TEXT,
  max_bid INTEGER,
  remaining_bids INTEGER,
  status INTEGER,
  reserve_price INTEGER,
  PRIMARY KEY (bidder_email_fk,listing_ID_fk),
  FOREIGN KEY (bidder_email_fk) REFERENCES Users(email_pk),
  FOREIGN KEY (listing_ID_fk) REFERENCES Auction_listings(listing_ID)
);


CREATE TABLE IF NOT EXISTS Watchlist(
    bidder_email_fk VARCHAR(255),
    seller_email_fk VARCHAR(255),
    listing_ID_fk INTEGER,
    PRIMARY KEY (bidder_email_fk, seller_email_fk, listing_ID_fk),
    FOREIGN KEY (bidder_email_fk) REFERENCES Bidders(email_fk),
    FOREIGN KEY (seller_email_fk, listing_ID_fk) REFERENCES Auction_Listings(seller_email_fk, listing_ID)
);

CREATE TABLE IF NOT EXISTS Promotions(
    promotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_email_fk VARCHAR(255) NOT NULL,
    listing_id_fk INTEGER NOT NULL,
    fee_paid    REAL NOT NULL,
    promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seller_email_fk, listing_id_fk)
        REFERENCES Auction_Listings(seller_email_fk, listing_ID)
);

