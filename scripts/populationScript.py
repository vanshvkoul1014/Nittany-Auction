import sqlite3
import os
from sqlite3 import Error
import csv

def populate():
    #Initiating a fresh database
    print("starting...")
    cnn = None #connection variable
    file = "nittanyauction.db" #name for the database
    dir = os.path.join(os.path.dirname(__file__), "..", "datasets")
    fileArray = []

    for csvFile in sorted(os.listdir(dir)):
        fileName = os.fsdecode(csvFile)
        fileArray.append(fileName)

    try:

        if os.path.exists(os.path.join(os.path.dirname(__file__), "nittanyauction.db")):
            os.remove(os.path.join(os.path.dirname(__file__), "nittanyauction.db"))

        with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r') as schema_file:
            sql = schema_file.read()
        cnn = sqlite3.connect(os.path.join(os.path.dirname(__file__), file)) #connecting to the database
        print("Db connection established")
        cs = cnn.cursor()
        cs.executescript(sql) #executing the schemas.sql file to define database schemas.
        cnn.commit()

        # code to populate the database:
        for file in fileArray: #iterating through all csv files in datasets directory
            nameLen = len(file)
            schemaName = os.path.splitext(file)[0] #omiting the .csv extenstion
            full_path = os.path.join(dir,file) #getting the full path name
            with open(full_path, mode = 'r', newline='') as csvfile: #reading csv file
                spamreader = csv.reader(csvfile, delimiter = ',')
                header = next(spamreader)

                placeHolders = ', '.join(['?']*len(header)) #placeholder to create the necessary amount of (?) as needed for cols
                query = f"INSERT INTO {schemaName} VALUES ({placeHolders})"

                if schemaName == 'Users':
                    import hashlib
                    for row in spamreader:
                        #hash the password w/ sha256 before inserting into DB
                        row[1] = hashlib.sha256(row[1].encode()).hexdigest()
                        #insert each hash one row at a time
                        cs.execute(query, row)
                else:
                    #all other tables, insert rows as is
                    cs.executemany(query, spamreader)

        cnn.commit()

        fixes = [
            ('Skirts', 'Clothing', 'Selby Mini Skirt'),
            ('Bodysuits', 'Clothing', 'Wilde Black Ribbed Long Sleeve Mock Neck Bodysuit'),
            ('T-Shirts', 'Clothing', 'Skeleton Hand Print Oversized tee'),
            ('Pants', 'Clothing', 'Ankle-length Leather Pants'),
            ('Jeans', 'Clothing', 'Skinny High Jeans'),
            ('Bath Robes', 'Clothing', 'Mainstays Satin Bathrobe'),
            ('Bath Robes', 'Clothing', 'Mainstays Waffled Bathrobe'),
            ('Iphone', 'Electrical Supplies', '13 Pro Max'),
            ('Samsung', 'Electrical Supplies', 'S22'),
            ('Samsung', 'Electrical Supplies', 'S23'),
            ('Apple Watch', 'Electrical Supplies', 'AW SE'),
            ('Apple Watch', 'Electrical Supplies', 'AW S7'),
            ('Wireless Headphones', 'Electrical Supplies', 'AirPods pro'),
            ('Wireless Headphones', 'Electrical Supplies', 'AirPods max'),
            ('Lip', 'Beauty Products', 'Sephora Rouge Gel Lip Liner'),
            ('Brushes & Applicators', 'Beauty Products', 'Rare Beauty Liquid Touch Brush'),
            ('Face', 'Beauty Products', 'Loreal Foundation Supreme'),
        ]

        for correct_cat, wrong_cat, product_name in fixes:
            cs.execute("""
                UPDATE Auction_Listings SET category_fk = ?
                WHERE category_fk = ? AND product_name = ?
            """, (correct_cat, wrong_cat, product_name))
        cnn.commit()


        try:
            cs.execute("ALTER TABLE Auction_Listings ADD COLUMN removal_reason TEXT")
            cnn.commit()
        except:
            pass #column already exists
    except Error as e:
        print(f"Data Base Error: {e}")
    except FileNotFoundError as e:
        print(f"File Not Found: {e}")


    finally:
        if cnn:
            cnn.close() #terminating connection
            print('done')


if __name__ == '__main__':
    populate()