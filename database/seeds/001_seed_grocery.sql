-- ============================================================================
-- SEED: GROCERY MASTER CATALOG (120+ realistic Indian products)
-- ============================================================================
-- Idempotent: uses ON CONFLICT(sku) DO NOTHING
-- ============================================================================

-- Suppliers first
INSERT INTO grocery_master.suppliers (supplier_code, supplier_name, contact_person, phone, email, city, state, pincode, gst_number, payment_terms)
VALUES
  ('GSUP-001', 'Reliance Wholesale', 'Rajesh Mehta', '9876543210', 'rajesh@reliancewholesale.in', 'Mumbai', 'Maharashtra', '400001', '27AABCR1234A1Z5', 'Net 30'),
  ('GSUP-002', 'Metro Cash & Carry', 'Priya Sharma', '9876543211', 'priya@metro.in', 'Bangalore', 'Karnataka', '560001', '29AABCM5678B2Z3', 'Net 15'),
  ('GSUP-003', 'Dmart Wholesale', 'Suresh Kumar', '9876543212', 'suresh@dmart.in', 'Pune', 'Maharashtra', '411001', '27AABCD9012C3Z1', 'Net 45'),
  ('GSUP-004', 'Kirana King Distributors', 'Amit Patel', '9876543213', 'amit@kiranaking.in', 'Ahmedabad', 'Gujarat', '380001', '24AABCK3456D4Z9', 'Net 30'),
  ('GSUP-005', 'Bharat FMCG Suppliers', 'Deepa Nair', '9876543214', 'deepa@bharatfmcg.in', 'Chennai', 'Tamil Nadu', '600001', '33AABCB7890E5Z7', 'Net 21')
ON CONFLICT (supplier_code) DO NOTHING;

-- Products
INSERT INTO grocery_master.products (sku, barcode, product_name, brand, category, subcategory, description, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage, is_active)
VALUES
  -- STAPLES (20)
  ('GRO-RICE-000001', '8901058001006', 'India Gate Basmati Rice', 'India Gate', 'Staples', 'Rice', 'Premium aged basmati rice, long grain', 'kg', '5 kg', 450.00, 380.00, 420.00, 5.00, TRUE),
  ('GRO-RICE-000002', '8901058001013', 'Daawat Rozana Basmati Rice', 'Daawat', 'Staples', 'Rice', 'Everyday basmati rice for daily cooking', 'kg', '5 kg', 350.00, 290.00, 330.00, 5.00, TRUE),
  ('GRO-RICE-000003', '8901058001020', 'Fortune Everyday Basmati Rice', 'Fortune', 'Staples', 'Rice', 'Steamed basmati rice', 'kg', '1 kg', 95.00, 75.00, 88.00, 5.00, TRUE),
  ('GRO-ATTA-000001', '8901725181017', 'Aashirvaad Superior MP Atta', 'Aashirvaad', 'Staples', 'Atta', '100% whole wheat flour, soft rotis', 'kg', '10 kg', 490.00, 410.00, 465.00, 5.00, TRUE),
  ('GRO-ATTA-000002', '8901725181024', 'Pillsbury Chakki Fresh Atta', 'Pillsbury', 'Staples', 'Atta', 'Fresh ground whole wheat atta', 'kg', '5 kg', 280.00, 230.00, 265.00, 5.00, TRUE),
  ('GRO-MAID-000001', '8901725181031', 'Maida All Purpose Flour', 'Aashirvaad', 'Staples', 'Maida', 'Refined wheat flour for baking', 'kg', '1 kg', 55.00, 42.00, 50.00, 5.00, TRUE),
  ('GRO-RAVA-000001', '8901725181048', 'Sooji Rava (Semolina)', 'Aashirvaad', 'Staples', 'Rava', 'Fine semolina for upma and halwa', 'kg', '1 kg', 65.00, 50.00, 60.00, 5.00, TRUE),
  ('GRO-POHA-000001', '8901725181055', 'Thin Poha (Flattened Rice)', 'Laxmi', 'Staples', 'Poha', 'Thin beaten rice flakes', 'kg', '500 g', 40.00, 30.00, 37.00, 5.00, TRUE),
  ('GRO-BESN-000001', '8901725181062', 'Besan (Gram Flour)', 'Aashirvaad', 'Staples', 'Besan', 'Fine gram flour for pakora and sweets', 'kg', '1 kg', 95.00, 75.00, 88.00, 5.00, TRUE),
  ('GRO-DAL-000001', '8901058002010', 'Toor Dal (Arhar)', 'Tata Sampann', 'Staples', 'Dal', 'Premium unpolished toor dal', 'kg', '1 kg', 180.00, 145.00, 170.00, 5.00, TRUE),
  ('GRO-DAL-000002', '8901058002027', 'Moong Dal', 'Tata Sampann', 'Staples', 'Dal', 'Yellow moong dal, split and washed', 'kg', '1 kg', 165.00, 130.00, 155.00, 5.00, TRUE),
  ('GRO-DAL-000003', '8901058002034', 'Chana Dal', 'Tata Sampann', 'Staples', 'Dal', 'Premium chana dal', 'kg', '1 kg', 120.00, 95.00, 112.00, 5.00, TRUE),
  ('GRO-DAL-000004', '8901058002041', 'Masoor Dal (Red Lentil)', 'Tata Sampann', 'Staples', 'Dal', 'Split red lentils', 'kg', '1 kg', 125.00, 100.00, 118.00, 5.00, TRUE),
  ('GRO-DAL-000005', '8901058002058', 'Urad Dal (Black Gram)', 'Tata Sampann', 'Staples', 'Dal', 'Split black gram dal', 'kg', '1 kg', 190.00, 155.00, 180.00, 5.00, TRUE),
  ('GRO-SUGR-000001', '8901058003010', 'Crystal Sugar', 'Uttam', 'Staples', 'Sugar', 'Refined white sugar', 'kg', '5 kg', 240.00, 200.00, 228.00, 5.00, TRUE),
  ('GRO-SALT-000001', '8901058004010', 'Tata Salt', 'Tata', 'Staples', 'Salt', 'Iodized vacuum evaporated salt', 'kg', '1 kg', 28.00, 22.00, 26.00, 5.00, TRUE),
  ('GRO-SALT-000002', '8901058004027', 'Tata Rock Salt', 'Tata', 'Staples', 'Salt', 'Sendha namak, rock salt', 'kg', '1 kg', 45.00, 35.00, 42.00, 5.00, TRUE),
  ('GRO-RAJM-000001', '8901058002065', 'Rajma (Kidney Beans)', 'Tata Sampann', 'Staples', 'Pulses', 'Jammu rajma, whole kidney beans', 'kg', '500 g', 90.00, 70.00, 85.00, 5.00, TRUE),
  ('GRO-CHOL-000001', '8901058002072', 'Kabuli Chana (Chickpeas)', 'Tata Sampann', 'Staples', 'Pulses', 'White chickpeas', 'kg', '500 g', 80.00, 62.00, 75.00, 5.00, TRUE),
  ('GRO-JGGR-000001', '8901058003027', 'Jaggery (Gur)', 'Uttam', 'Staples', 'Sweetener', 'Organic sugarcane jaggery', 'kg', '1 kg', 90.00, 70.00, 85.00, 5.00, TRUE),

  -- SPICES (15)
  ('GRO-TURM-000001', '8901063061019', 'Turmeric Powder (Haldi)', 'Everest', 'Spices', 'Turmeric', 'Pure turmeric powder', 'g', '100 g', 52.00, 40.00, 48.00, 5.00, TRUE),
  ('GRO-CHIL-000001', '8901063061026', 'Red Chilli Powder', 'Everest', 'Spices', 'Chilli', 'Hot red chilli powder', 'g', '100 g', 60.00, 46.00, 55.00, 5.00, TRUE),
  ('GRO-CHIL-000002', '8901063061033', 'Kashmiri Chilli Powder', 'Everest', 'Spices', 'Chilli', 'Mild red colour, less heat', 'g', '100 g', 75.00, 58.00, 70.00, 5.00, TRUE),
  ('GRO-CORR-000001', '8901063061040', 'Coriander Powder (Dhaniya)', 'Everest', 'Spices', 'Coriander', 'Ground coriander seeds', 'g', '100 g', 45.00, 34.00, 42.00, 5.00, TRUE),
  ('GRO-CUMM-000001', '8901063061057', 'Cumin Powder (Jeera)', 'Everest', 'Spices', 'Cumin', 'Roasted cumin powder', 'g', '100 g', 85.00, 66.00, 80.00, 5.00, TRUE),
  ('GRO-BPEP-000001', '8901063061064', 'Black Pepper Whole', 'Everest', 'Spices', 'Pepper', 'Whole Malabar black pepper', 'g', '100 g', 120.00, 95.00, 112.00, 5.00, TRUE),
  ('GRO-GARM-000001', '8901063061071', 'Garam Masala', 'Everest', 'Spices', 'Masala', 'Aromatic spice blend', 'g', '100 g', 90.00, 70.00, 85.00, 5.00, TRUE),
  ('GRO-KITK-000001', '8901063061088', 'Kitchen King Masala', 'MDH', 'Spices', 'Masala', 'All-purpose curry masala', 'g', '100 g', 75.00, 58.00, 70.00, 5.00, TRUE),
  ('GRO-CHAT-000001', '8901063061095', 'Chaat Masala', 'MDH', 'Spices', 'Masala', 'Tangy chaat masala', 'g', '100 g', 55.00, 42.00, 50.00, 5.00, TRUE),
  ('GRO-PVBM-000001', '8901063061102', 'Pav Bhaji Masala', 'Everest', 'Spices', 'Masala', 'Special pav bhaji spice mix', 'g', '100 g', 65.00, 50.00, 60.00, 5.00, TRUE),
  ('GRO-CHLM-000001', '8901063061119', 'Chole Masala', 'MDH', 'Spices', 'Masala', 'Punjabi chole masala blend', 'g', '100 g', 60.00, 46.00, 55.00, 5.00, TRUE),
  ('GRO-RAJM-000002', '8901063061126', 'Rajma Masala', 'MDH', 'Spices', 'Masala', 'Rajma curry masala', 'g', '100 g', 60.00, 46.00, 55.00, 5.00, TRUE),
  ('GRO-BIRM-000001', '8901063061133', 'Biryani Masala', 'Everest', 'Spices', 'Masala', 'Hyderabadi biryani masala', 'g', '50 g', 65.00, 50.00, 60.00, 5.00, TRUE),
  ('GRO-MUST-000001', '8901063061140', 'Mustard Seeds (Rai)', 'Everest', 'Spices', 'Seeds', 'Black mustard seeds for tempering', 'g', '100 g', 30.00, 22.00, 27.00, 5.00, TRUE),
  ('GRO-CLOV-000001', '8901063061157', 'Clove (Laung)', 'Everest', 'Spices', 'Whole Spice', 'Whole cloves', 'g', '50 g', 110.00, 88.00, 102.00, 5.00, TRUE),

  -- SNACKS (15)
  ('GRO-BISC-000001', '8901012503001', 'Parle-G Gold Biscuits', 'Parle', 'Snacks', 'Biscuits', 'Glucose biscuits, iconic Indian brand', 'pack', '1 kg', 90.00, 72.00, 85.00, 18.00, TRUE),
  ('GRO-BISC-000002', '8901012503018', 'Britannia Good Day Cashew', 'Britannia', 'Snacks', 'Biscuits', 'Cashew cookies', 'pack', '250 g', 50.00, 40.00, 47.00, 18.00, TRUE),
  ('GRO-BISC-000003', '8901012503025', 'Britannia Marie Gold', 'Britannia', 'Snacks', 'Biscuits', 'Light tea-time biscuit', 'pack', '250 g', 40.00, 32.00, 38.00, 18.00, TRUE),
  ('GRO-BISC-000004', '8901012503032', 'Sunfeast Dark Fantasy', 'Sunfeast', 'Snacks', 'Biscuits', 'Chocolate filled cookies', 'pack', '300 g', 120.00, 95.00, 112.00, 18.00, TRUE),
  ('GRO-CHIP-000001', '8901491101011', 'Lays Classic Salted Chips', 'Lays', 'Snacks', 'Chips', 'Classic salted potato chips', 'pack', '52 g', 20.00, 16.00, 19.00, 12.00, TRUE),
  ('GRO-CHIP-000002', '8901491101028', 'Lays Magic Masala Chips', 'Lays', 'Snacks', 'Chips', 'Indian magic masala flavour', 'pack', '52 g', 20.00, 16.00, 19.00, 12.00, TRUE),
  ('GRO-CHIP-000003', '8901491101035', 'Kurkure Masala Munch', 'Kurkure', 'Snacks', 'Namkeen', 'Crunchy corn puff snack', 'pack', '94 g', 20.00, 16.00, 19.00, 12.00, TRUE),
  ('GRO-NAMK-000001', '8901063065017', 'Haldiram Bhujia', 'Haldiram', 'Snacks', 'Namkeen', 'Traditional besan bhujia', 'pack', '400 g', 120.00, 95.00, 112.00, 12.00, TRUE),
  ('GRO-NAMK-000002', '8901063065024', 'Haldiram Aloo Bhujia', 'Haldiram', 'Snacks', 'Namkeen', 'Potato sev namkeen', 'pack', '200 g', 65.00, 50.00, 60.00, 12.00, TRUE),
  ('GRO-NAMK-000003', '8901063065031', 'Haldiram Moong Dal', 'Haldiram', 'Snacks', 'Namkeen', 'Fried moong dal snack', 'pack', '200 g', 60.00, 46.00, 55.00, 12.00, TRUE),
  ('GRO-NOOD-000001', '8901058005010', 'Maggi 2-Minute Noodles', 'Maggi', 'Snacks', 'Instant Noodles', 'Masala instant noodles', 'pack', '280 g (4-pack)', 56.00, 44.00, 52.00, 18.00, TRUE),
  ('GRO-NOOD-000002', '8901058005027', 'Yippee Noodles Magic Masala', 'Yippee', 'Snacks', 'Instant Noodles', 'Round block instant noodles', 'pack', '280 g (4-pack)', 52.00, 41.00, 48.00, 18.00, TRUE),
  ('GRO-WAFF-000001', '8901012503049', 'Britannia Wafers Cheese', 'Britannia', 'Snacks', 'Wafers', 'Cheese flavoured wafer biscuits', 'pack', '75 g', 30.00, 24.00, 28.00, 18.00, TRUE),
  ('GRO-POPC-000001', '8901491101042', 'Act II Butter Popcorn', 'Act II', 'Snacks', 'Popcorn', 'Microwave butter popcorn', 'pack', '106 g', 50.00, 40.00, 47.00, 12.00, TRUE),
  ('GRO-COOK-000001', '8901012503056', 'Hide & Seek Chocolate Chip', 'Parle', 'Snacks', 'Cookies', 'Chocolate chip cookies', 'pack', '200 g', 50.00, 40.00, 47.00, 18.00, TRUE),

  -- BEVERAGES (12)
  ('GRO-TEA-000001', '8901058006010', 'Tata Tea Gold', 'Tata Tea', 'Beverages', 'Tea', 'Premium leaf tea', 'g', '500 g', 295.00, 240.00, 280.00, 5.00, TRUE),
  ('GRO-TEA-000002', '8901058006027', 'Red Label Natural Care', 'Brooke Bond', 'Beverages', 'Tea', 'Tea with ayurvedic herbs', 'g', '500 g', 275.00, 225.00, 260.00, 5.00, TRUE),
  ('GRO-COFF-000001', '8901058007010', 'Nescafe Classic Coffee', 'Nescafe', 'Beverages', 'Coffee', 'Instant coffee powder', 'g', '200 g', 440.00, 360.00, 415.00, 18.00, TRUE),
  ('GRO-COFF-000002', '8901058007027', 'Bru Instant Coffee', 'Bru', 'Beverages', 'Coffee', 'Roasted instant coffee', 'g', '200 g', 380.00, 310.00, 360.00, 18.00, TRUE),
  ('GRO-SODA-000001', '8901058008010', 'Coca-Cola', 'Coca-Cola', 'Beverages', 'Soft Drinks', 'Carbonated cola drink', 'ml', '750 ml', 40.00, 32.00, 38.00, 28.00, TRUE),
  ('GRO-SODA-000002', '8901058008027', 'Thumbs Up', 'Thumbs Up', 'Beverages', 'Soft Drinks', 'Strong cola drink', 'ml', '750 ml', 40.00, 32.00, 38.00, 28.00, TRUE),
  ('GRO-JUIC-000001', '8901058009010', 'Real Mango Juice', 'Real', 'Beverages', 'Juice', 'Alphonso mango fruit juice', 'ml', '1 L', 120.00, 95.00, 112.00, 12.00, TRUE),
  ('GRO-JUIC-000002', '8901058009027', 'Tropicana Mixed Fruit', 'Tropicana', 'Beverages', 'Juice', 'Mixed fruit juice, no added sugar', 'ml', '1 L', 110.00, 88.00, 102.00, 12.00, TRUE),
  ('GRO-WATR-000001', '8901058010010', 'Bisleri Mineral Water', 'Bisleri', 'Beverages', 'Water', 'Packaged drinking water', 'ml', '1 L', 20.00, 12.00, 18.00, 18.00, TRUE),
  ('GRO-ENRG-000001', '8901058010027', 'Red Bull Energy Drink', 'Red Bull', 'Beverages', 'Energy Drinks', 'Energy drink with taurine', 'ml', '250 ml', 125.00, 100.00, 118.00, 28.00, TRUE),
  ('GRO-MLKD-000001', '8901058010034', 'Amul Kool Badam Milk', 'Amul', 'Beverages', 'Flavoured Milk', 'Badam flavoured milk drink', 'ml', '200 ml', 30.00, 24.00, 28.00, 12.00, TRUE),
  ('GRO-BNAV-000001', '8901058010041', 'Horlicks Classic Malt', 'Horlicks', 'Beverages', 'Health Drinks', 'Health food drink malt flavour', 'g', '500 g', 310.00, 250.00, 295.00, 18.00, TRUE),

  -- DAIRY (8)
  ('GRO-MILK-000001', '8901058011010', 'Amul Gold Full Cream Milk', 'Amul', 'Dairy', 'Milk', 'Full cream pasteurized milk', 'ml', '500 ml', 34.00, 28.00, 32.00, 0.00, TRUE),
  ('GRO-CURD-000001', '8901058011027', 'Amul Masti Dahi', 'Amul', 'Dairy', 'Curd', 'Fresh set curd', 'g', '400 g', 40.00, 32.00, 38.00, 0.00, TRUE),
  ('GRO-BUTR-000001', '8901058011034', 'Amul Butter', 'Amul', 'Dairy', 'Butter', 'Pasteurized salted butter', 'g', '500 g', 280.00, 230.00, 265.00, 12.00, TRUE),
  ('GRO-CHEE-000001', '8901058011041', 'Amul Cheese Slices', 'Amul', 'Dairy', 'Cheese', 'Processed cheese slices', 'pack', '200 g (10 slices)', 120.00, 95.00, 112.00, 12.00, TRUE),
  ('GRO-PANR-000001', '8901058011058', 'Amul Fresh Paneer', 'Amul', 'Dairy', 'Paneer', 'Fresh cottage cheese block', 'g', '200 g', 90.00, 72.00, 85.00, 0.00, TRUE),
  ('GRO-GHEE-000001', '8901058011065', 'Amul Pure Ghee', 'Amul', 'Dairy', 'Ghee', 'Pure cow ghee', 'ml', '500 ml', 310.00, 255.00, 295.00, 12.00, TRUE),
  ('GRO-CREM-000001', '8901058011072', 'Amul Fresh Cream', 'Amul', 'Dairy', 'Cream', 'Fresh dairy cream for cooking', 'ml', '200 ml', 45.00, 36.00, 42.00, 12.00, TRUE),
  ('GRO-LASI-000001', '8901058011089', 'Amul Kool Lassi', 'Amul', 'Dairy', 'Lassi', 'Rose flavoured lassi drink', 'ml', '200 ml', 25.00, 20.00, 23.00, 0.00, TRUE),

  -- COOKING OIL (6)
  ('GRO-OIL-000001', '8901058012010', 'Fortune Sunlite Sunflower Oil', 'Fortune', 'Cooking Oil', 'Sunflower', 'Refined sunflower cooking oil', 'L', '1 L', 150.00, 125.00, 142.00, 5.00, TRUE),
  ('GRO-OIL-000002', '8901058012027', 'Fortune Soyabean Oil', 'Fortune', 'Cooking Oil', 'Soybean', 'Refined soybean oil', 'L', '1 L', 130.00, 108.00, 122.00, 5.00, TRUE),
  ('GRO-OIL-000003', '8901058012034', 'Saffola Gold Oil', 'Saffola', 'Cooking Oil', 'Blended', 'Pro healthy blended edible oil', 'L', '1 L', 195.00, 160.00, 185.00, 5.00, TRUE),
  ('GRO-OIL-000004', '8901058012041', 'Dalda Vanaspati Ghee', 'Dalda', 'Cooking Oil', 'Vanaspati', 'Hydrogenated vegetable oil', 'kg', '1 kg', 130.00, 105.00, 122.00, 5.00, TRUE),
  ('GRO-OIL-000005', '8901058012058', 'Dhara Mustard Oil', 'Dhara', 'Cooking Oil', 'Mustard', 'Kachi ghani mustard oil', 'L', '1 L', 185.00, 150.00, 175.00, 5.00, TRUE),
  ('GRO-OIL-000006', '8901058012065', 'KLF Coconut Oil', 'KLF Coconad', 'Cooking Oil', 'Coconut', 'Pure coconut cooking oil', 'ml', '500 ml', 120.00, 95.00, 112.00, 5.00, TRUE),

  -- PERSONAL CARE (10)
  ('GRO-SOAP-000001', '8901058013010', 'Lux Soft Touch Soap', 'Lux', 'Personal Care', 'Soap', 'French rose and almond oil soap', 'pack', '100 g', 42.00, 34.00, 40.00, 18.00, TRUE),
  ('GRO-SOAP-000002', '8901058013027', 'Dettol Original Soap', 'Dettol', 'Personal Care', 'Soap', 'Antibacterial protection soap', 'pack', '125 g', 52.00, 42.00, 49.00, 18.00, TRUE),
  ('GRO-SHMP-000001', '8901058013034', 'Head & Shoulders Anti-Dandruff', 'Head & Shoulders', 'Personal Care', 'Shampoo', 'Anti-dandruff shampoo', 'ml', '340 ml', 310.00, 250.00, 295.00, 18.00, TRUE),
  ('GRO-SHMP-000002', '8901058013041', 'Clinic Plus Strong & Long', 'Clinic Plus', 'Personal Care', 'Shampoo', 'Protein shampoo for long hair', 'ml', '175 ml', 110.00, 88.00, 102.00, 18.00, TRUE),
  ('GRO-TPST-000001', '8901058013058', 'Colgate MaxFresh Toothpaste', 'Colgate', 'Personal Care', 'Toothpaste', 'Cooling crystal gel toothpaste', 'g', '150 g', 92.00, 74.00, 87.00, 18.00, TRUE),
  ('GRO-TBRH-000001', '8901058013065', 'Colgate Slim Soft Toothbrush', 'Colgate', 'Personal Care', 'Toothbrush', 'Ultra soft bristle toothbrush', 'unit', '1 pc', 55.00, 44.00, 52.00, 18.00, TRUE),
  ('GRO-DEOD-000001', '8901058013072', 'Wild Stone Deodorant', 'Wild Stone', 'Personal Care', 'Deodorant', 'Body spray for men', 'ml', '150 ml', 225.00, 180.00, 212.00, 28.00, TRUE),
  ('GRO-FACW-000001', '8901058013079', 'Himalaya Neem Face Wash', 'Himalaya', 'Personal Care', 'Face Wash', 'Purifying neem face wash', 'ml', '150 ml', 175.00, 140.00, 165.00, 18.00, TRUE),
  ('GRO-HAND-000001', '8901058013086', 'Dettol Hand Sanitizer', 'Dettol', 'Personal Care', 'Sanitizer', 'Instant hand sanitizer', 'ml', '200 ml', 130.00, 105.00, 122.00, 18.00, TRUE),
  ('GRO-HAIO-000001', '8901058013093', 'Parachute Coconut Hair Oil', 'Parachute', 'Personal Care', 'Hair Oil', 'Pure coconut oil', 'ml', '300 ml', 175.00, 140.00, 165.00, 18.00, TRUE),

  -- HOUSEHOLD (10)
  ('GRO-DETG-000001', '8901058014010', 'Surf Excel Easy Wash', 'Surf Excel', 'Household', 'Detergent', 'Washing powder for clothes', 'kg', '1 kg', 145.00, 118.00, 138.00, 18.00, TRUE),
  ('GRO-DETG-000002', '8901058014027', 'Tide Plus Jasmine & Rose', 'Tide', 'Household', 'Detergent', 'Detergent powder with fragrance', 'kg', '1 kg', 135.00, 108.00, 128.00, 18.00, TRUE),
  ('GRO-DISH-000001', '8901058014034', 'Vim Dishwash Liquid', 'Vim', 'Household', 'Dishwash', 'Lemon dishwashing liquid', 'ml', '500 ml', 95.00, 76.00, 90.00, 18.00, TRUE),
  ('GRO-DISH-000002', '8901058014041', 'Vim Dishwash Bar', 'Vim', 'Household', 'Dishwash', 'Lemon dishwash bar', 'g', '300 g', 30.00, 24.00, 28.00, 18.00, TRUE),
  ('GRO-FLCL-000001', '8901058014058', 'Lizol Floor Cleaner', 'Lizol', 'Household', 'Floor Cleaner', 'Citrus surface cleaner', 'ml', '500 ml', 115.00, 92.00, 108.00, 18.00, TRUE),
  ('GRO-TLCL-000001', '8901058014065', 'Harpic Toilet Cleaner', 'Harpic', 'Household', 'Toilet Cleaner', 'Power plus disinfectant', 'ml', '500 ml', 92.00, 74.00, 87.00, 18.00, TRUE),
  ('GRO-GARB-000001', '8901058014072', 'Ezee Garbage Bags', 'Ezee', 'Household', 'Garbage Bags', 'Biodegradable garbage bags', 'pack', '30 bags (Medium)', 80.00, 64.00, 75.00, 18.00, TRUE),
  ('GRO-TISS-000001', '8901058014079', 'Kleenex Tissue Paper', 'Kleenex', 'Household', 'Tissue', 'Soft facial tissue box', 'pack', '100 pulls', 85.00, 68.00, 80.00, 18.00, TRUE),
  ('GRO-MOPT-000001', '8901058014086', 'Scotch-Brite Scrub Pad', 'Scotch-Brite', 'Household', 'Cleaning', 'Heavy duty scrub pad', 'pack', '3 pcs', 60.00, 48.00, 56.00, 18.00, TRUE),
  ('GRO-NAPH-000001', '8901058014093', 'Odonil Room Freshener', 'Odonil', 'Household', 'Freshener', 'Bathroom air freshener blocks', 'pack', '75 g', 55.00, 44.00, 52.00, 28.00, TRUE),

  -- SAUCES & CONDIMENTS (10)
  ('GRO-KTCH-000001', '8901058015010', 'Kissan Tomato Ketchup', 'Kissan', 'Sauces', 'Ketchup', 'Rich tomato ketchup', 'g', '950 g', 155.00, 125.00, 145.00, 12.00, TRUE),
  ('GRO-KTCH-000002', '8901058015027', 'Maggi Hot & Sweet Sauce', 'Maggi', 'Sauces', 'Chilli Sauce', 'Tomato chilli sauce', 'g', '500 g', 115.00, 92.00, 108.00, 12.00, TRUE),
  ('GRO-SOSC-000001', '8901058015034', 'Ching''s Soy Sauce', 'Ching''s', 'Sauces', 'Soy Sauce', 'Dark soy sauce', 'ml', '210 ml', 60.00, 48.00, 56.00, 12.00, TRUE),
  ('GRO-MAYO-000001', '8901058015041', 'Hellmann''s Eggless Mayonnaise', 'Hellmann''s', 'Sauces', 'Mayonnaise', 'Creamy eggless mayo', 'g', '250 g', 120.00, 96.00, 112.00, 12.00, TRUE),
  ('GRO-VINR-000001', '8901058015058', 'American Garden White Vinegar', 'American Garden', 'Sauces', 'Vinegar', 'White distilled vinegar', 'ml', '473 ml', 120.00, 96.00, 112.00, 18.00, TRUE),
  ('GRO-MUST-000002', '8901058015065', 'American Garden Mustard Sauce', 'American Garden', 'Sauces', 'Mustard Sauce', 'Yellow mustard squeeze', 'g', '227 g', 135.00, 108.00, 128.00, 18.00, TRUE),
  ('GRO-PICK-000001', '8901058015072', 'Mother''s Recipe Mango Pickle', 'Mother''s Recipe', 'Sauces', 'Pickle', 'Rajasthani mango pickle', 'g', '500 g', 140.00, 112.00, 132.00, 12.00, TRUE),
  ('GRO-PICK-000002', '8901058015079', 'Priya Mixed Vegetable Pickle', 'Priya', 'Sauces', 'Pickle', 'South Indian style mixed pickle', 'g', '300 g', 80.00, 64.00, 75.00, 12.00, TRUE),
  ('GRO-JAM-000001', '8901058015086', 'Kissan Mixed Fruit Jam', 'Kissan', 'Sauces', 'Jam', 'Real fruit mixed jam', 'g', '500 g', 180.00, 145.00, 170.00, 18.00, TRUE),
  ('GRO-HNNY-000001', '8901058015093', 'Dabur Honey', 'Dabur', 'Sauces', 'Honey', '100% pure honey', 'g', '500 g', 280.00, 225.00, 265.00, 0.00, TRUE)

ON CONFLICT (sku) DO NOTHING;
