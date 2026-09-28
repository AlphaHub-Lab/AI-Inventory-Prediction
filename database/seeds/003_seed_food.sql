-- ============================================================================
-- SEED: FOOD MASTER CATALOG (115+ realistic Indian food products)
-- ============================================================================

-- Suppliers
INSERT INTO food_master.suppliers (supplier_code, supplier_name, contact_person, phone, email, city, state, pincode, gst_number, payment_terms)
VALUES
  ('FSUP-001', 'FreshMart Wholesale', 'Vikram Desai', '9877543210', 'vikram@freshmart.in', 'Mumbai', 'Maharashtra', '400001', '27AABCF1234K1Z5', 'Net 7'),
  ('FSUP-002', 'Agri Fresh Suppliers', 'Lakshmi Iyer', '9877543211', 'lakshmi@agrifresh.in', 'Coimbatore', 'Tamil Nadu', '641001', '33AABCA5678L2Z3', 'Net 15'),
  ('FSUP-003', 'Cold Chain Express', 'Arjun Sethi', '9877543212', 'arjun@coldchain.in', 'Delhi', 'Delhi', '110055', '07AABCC9012M3Z1', 'Net 10'),
  ('FSUP-004', 'Bakery Ingredients Co.', 'Meera Kapoor', '9877543213', 'meera@bakeryingredients.in', 'Bangalore', 'Karnataka', '560034', '29AABCB3456N4Z9', 'Net 21'),
  ('FSUP-005', 'Indian Dairy Federation', 'Gopal Agarwal', '9877543214', 'gopal@idf.in', 'Anand', 'Gujarat', '388001', '24AABCI7890O5Z7', 'Net 7')
ON CONFLICT (supplier_code) DO NOTHING;

-- Products
INSERT INTO food_master.products (sku, barcode, product_name, brand, category, subcategory, description, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage, is_active)
VALUES
  -- RAW INGREDIENTS (15)
  ('FOOD-RICE-000001', '8902001001001', 'Sona Masoori Raw Rice', 'India Gate', 'Raw Ingredients', 'Rice', 'South Indian sona masoori rice', 'kg', '5 kg', 320.00, 265.00, 305.00, 5.00, TRUE),
  ('FOOD-RICE-000002', '8902001001002', 'Brown Rice Organic', 'Organic Tattva', 'Raw Ingredients', 'Rice', 'Unpolished organic brown rice', 'kg', '1 kg', 150.00, 118.00, 140.00, 5.00, TRUE),
  ('FOOD-FLOR-000001', '8902001001003', 'Multigrain Atta', 'Aashirvaad', 'Raw Ingredients', 'Flour', 'Multigrain whole wheat flour', 'kg', '5 kg', 310.00, 255.00, 295.00, 5.00, TRUE),
  ('FOOD-OATS-000001', '8902001001004', 'Rolled Oats', 'Quaker', 'Raw Ingredients', 'Cereal', 'Whole grain rolled oats', 'g', '1 kg', 280.00, 220.00, 265.00, 5.00, TRUE),
  ('FOOD-QNOA-000001', '8902001001005', 'White Quinoa', 'True Elements', 'Raw Ingredients', 'Superfoods', 'Imported white quinoa grains', 'g', '500 g', 350.00, 275.00, 330.00, 5.00, TRUE),
  ('FOOD-OLIV-000001', '8902001001006', 'Extra Virgin Olive Oil', 'Borges', 'Raw Ingredients', 'Oil', 'Cold pressed extra virgin olive oil', 'ml', '500 ml', 550.00, 430.00, 520.00, 5.00, TRUE),
  ('FOOD-SUGR-000001', '8902001001007', 'Organic Jaggery Powder', 'Organic Tattva', 'Raw Ingredients', 'Sweetener', 'Chemical-free jaggery powder', 'g', '500 g', 120.00, 92.00, 112.00, 5.00, TRUE),
  ('FOOD-COCO-000001', '8902001001008', 'Desiccated Coconut', 'Eastern', 'Raw Ingredients', 'Baking', 'Fine desiccated coconut powder', 'g', '200 g', 70.00, 52.00, 65.00, 5.00, TRUE),
  ('FOOD-SEML-000001', '8902001001009', 'Fine Semolina', 'Aashirvaad', 'Raw Ingredients', 'Flour', 'Bansi rava / fine semolina', 'g', '500 g', 45.00, 34.00, 42.00, 5.00, TRUE),
  ('FOOD-COCB-000001', '8902001001010', 'Cocoa Butter Chips', 'Morde', 'Raw Ingredients', 'Baking', 'Premium cocoa butter for baking', 'g', '200 g', 250.00, 190.00, 235.00, 18.00, TRUE),
  ('FOOD-CHOC-000001', '8902001001011', 'Dark Cooking Chocolate', 'Morde', 'Raw Ingredients', 'Baking', 'Dark compound chocolate slab', 'g', '500 g', 180.00, 138.00, 170.00, 18.00, TRUE),
  ('FOOD-YELW-000001', '8902001001012', 'Yellow Butter (Cooking)', 'Amul', 'Raw Ingredients', 'Dairy', 'Salted cooking butter block', 'g', '500 g', 280.00, 230.00, 265.00, 12.00, TRUE),
  ('FOOD-CREM-000001', '8902001001013', 'Whipping Cream', 'Rich', 'Raw Ingredients', 'Dairy', 'Non-dairy whipping cream', 'ml', '1 L', 350.00, 275.00, 330.00, 18.00, TRUE),
  ('FOOD-YEST-000001', '8902001001014', 'Active Dry Yeast', 'Gloripan', 'Raw Ingredients', 'Baking', 'Instant active dry yeast', 'g', '500 g', 180.00, 138.00, 170.00, 12.00, TRUE),
  ('FOOD-BKPW-000001', '8902001001015', 'Baking Powder', 'Weikfield', 'Raw Ingredients', 'Baking', 'Double acting baking powder', 'g', '100 g', 40.00, 28.00, 37.00, 18.00, TRUE),

  -- PACKAGED FOOD (20)
  ('FOOD-CRNF-000001', '8902001002001', 'Corn Flakes Original', 'Kellogg''s', 'Packaged Food', 'Cereal', 'Crispy corn flakes breakfast cereal', 'g', '475 g', 210.00, 165.00, 198.00, 18.00, TRUE),
  ('FOOD-MUSL-000001', '8902001002002', 'Crunchy Muesli Fruit & Nut', 'Bagrry''s', 'Packaged Food', 'Cereal', 'Oat muesli with dried fruits and nuts', 'g', '750 g', 420.00, 330.00, 398.00, 18.00, TRUE),
  ('FOOD-PAST-000001', '8902001002003', 'Penne Pasta', 'Borges', 'Packaged Food', 'Pasta', 'Durum wheat penne rigate', 'g', '500 g', 160.00, 125.00, 150.00, 12.00, TRUE),
  ('FOOD-PAST-000002', '8902001002004', 'Spaghetti', 'Del Monte', 'Packaged Food', 'Pasta', 'Durum wheat spaghetti', 'g', '500 g', 145.00, 112.00, 138.00, 12.00, TRUE),
  ('FOOD-SOUP-000001', '8902001002005', 'Tomato Soup Instant', 'Knorr', 'Packaged Food', 'Soup', 'Classic tomato soup mix', 'g', '53 g', 40.00, 30.00, 37.00, 18.00, TRUE),
  ('FOOD-SOUP-000002', '8902001002006', 'Hot & Sour Soup', 'Ching''s', 'Packaged Food', 'Soup', 'Instant hot and sour veg soup', 'g', '55 g', 35.00, 26.00, 32.00, 18.00, TRUE),
  ('FOOD-PCKL-000001', '8902001002007', 'Aam Ka Achaar', 'Mother''s Recipe', 'Packaged Food', 'Pickle', 'Traditional mango pickle', 'g', '500 g', 140.00, 108.00, 132.00, 12.00, TRUE),
  ('FOOD-PPRD-000001', '8902001002008', 'Moong Dal Papad', 'Lijjat', 'Packaged Food', 'Papad', 'Crispy moong dal papad', 'g', '200 g', 60.00, 45.00, 55.00, 5.00, TRUE),
  ('FOOD-CKNG-000001', '8902001002009', 'Coconut Milk', 'KLF', 'Packaged Food', 'Canned', 'UHT coconut milk', 'ml', '400 ml', 120.00, 92.00, 112.00, 12.00, TRUE),
  ('FOOD-BEAN-000001', '8902001002010', 'Baked Beans', 'Del Monte', 'Packaged Food', 'Canned', 'Baked beans in tomato sauce', 'g', '450 g', 165.00, 128.00, 155.00, 12.00, TRUE),
  ('FOOD-CORN-000001', '8902001002011', 'Sweet Corn Kernels', 'Del Monte', 'Packaged Food', 'Canned', 'Canned sweet corn in brine', 'g', '420 g', 150.00, 116.00, 142.00, 12.00, TRUE),
  ('FOOD-SAUC-000001', '8902001002012', 'Pasta Sauce Arrabiata', 'Del Monte', 'Packaged Food', 'Sauces', 'Italian pasta sauce spicy', 'g', '400 g', 175.00, 135.00, 165.00, 12.00, TRUE),
  ('FOOD-PSBT-000001', '8902001002013', 'Peanut Butter Crunchy', 'Pintola', 'Packaged Food', 'Spreads', 'Natural crunchy peanut butter', 'g', '350 g', 290.00, 225.00, 275.00, 12.00, TRUE),
  ('FOOD-HNNY-000001', '8902001002014', 'Raw Honey Organic', 'Apis', 'Packaged Food', 'Spreads', 'Unprocessed organic wild honey', 'g', '500 g', 350.00, 275.00, 330.00, 0.00, TRUE),
  ('FOOD-CHKL-000001', '8902001002015', 'Dark Chocolate 70%', 'Amul', 'Packaged Food', 'Confectionery', 'Dark chocolate bar 70% cocoa', 'g', '150 g', 140.00, 108.00, 132.00, 28.00, TRUE),
  ('FOOD-DRFR-000001', '8902001002016', 'Trail Mix Premium', 'Happilo', 'Packaged Food', 'Dry Fruits', 'Mixed nuts and dried fruits', 'g', '200 g', 280.00, 218.00, 265.00, 12.00, TRUE),
  ('FOOD-DRFR-000002', '8902001002017', 'Roasted Almonds Salted', 'Happilo', 'Packaged Food', 'Dry Fruits', 'California almonds roasted salted', 'g', '200 g', 320.00, 250.00, 305.00, 12.00, TRUE),
  ('FOOD-DRFR-000003', '8902001002018', 'Cashew Whole W240', 'Nutraj', 'Packaged Food', 'Dry Fruits', 'Premium whole cashew nuts', 'g', '250 g', 380.00, 298.00, 360.00, 12.00, TRUE),
  ('FOOD-CHIP-000001', '8902001002019', 'Banana Chips Kerala', 'Kerala Chips', 'Packaged Food', 'Snacks', 'Traditional Kerala banana chips', 'g', '250 g', 90.00, 68.00, 85.00, 12.00, TRUE),
  ('FOOD-MURA-000001', '8902001002020', 'Murukku South Indian', 'Aachi', 'Packaged Food', 'Snacks', 'Crispy rice flour murukku', 'g', '200 g', 75.00, 56.00, 70.00, 12.00, TRUE),

  -- READY TO EAT (10)
  ('FOOD-RTE-000001', '8902001003001', 'Dal Makhani Ready Meal', 'MTR', 'Ready to Eat', 'Indian Main', 'Heat and eat dal makhani', 'g', '300 g', 99.00, 75.00, 93.00, 12.00, TRUE),
  ('FOOD-RTE-000002', '8902001003002', 'Paneer Butter Masala', 'MTR', 'Ready to Eat', 'Indian Main', 'Heat and eat paneer curry', 'g', '300 g', 110.00, 84.00, 104.00, 12.00, TRUE),
  ('FOOD-RTE-000003', '8902001003003', 'Rajma Masala Ready Meal', 'Haldiram', 'Ready to Eat', 'Indian Main', 'Kidney bean curry, microwave ready', 'g', '300 g', 95.00, 72.00, 90.00, 12.00, TRUE),
  ('FOOD-RTE-000004', '8902001003004', 'Upma Instant Mix', 'MTR', 'Ready to Eat', 'Breakfast', 'Instant rava upma mix', 'g', '180 g', 55.00, 42.00, 52.00, 18.00, TRUE),
  ('FOOD-RTE-000005', '8902001003005', 'Poha Instant Mix', 'MTR', 'Ready to Eat', 'Breakfast', 'Instant poha mix', 'g', '180 g', 50.00, 38.00, 47.00, 18.00, TRUE),
  ('FOOD-RTE-000006', '8902001003006', 'Gulab Jamun Mix', 'Gits', 'Ready to Eat', 'Dessert', 'Instant gulab jamun mix', 'g', '200 g', 85.00, 65.00, 80.00, 18.00, TRUE),
  ('FOOD-RTE-000007', '8902001003007', 'Ras Malai Mix', 'Gits', 'Ready to Eat', 'Dessert', 'Instant rasmalai mix', 'g', '150 g', 95.00, 72.00, 90.00, 18.00, TRUE),
  ('FOOD-RTE-000008', '8902001003008', 'Dosa Batter Fresh', 'iD Fresh', 'Ready to Eat', 'Breakfast', 'Stone ground dosa batter', 'g', '1 kg', 65.00, 50.00, 62.00, 5.00, TRUE),
  ('FOOD-RTE-000009', '8902001003009', 'Idli Batter Fresh', 'iD Fresh', 'Ready to Eat', 'Breakfast', 'Stone ground idli batter', 'g', '1 kg', 60.00, 46.00, 57.00, 5.00, TRUE),
  ('FOOD-RTE-000010', '8902001003010', 'Chapati Pack Fresh', 'iD Fresh', 'Ready to Eat', 'Bread', 'Whole wheat ready chapati', 'pack', '10 pcs', 55.00, 42.00, 52.00, 5.00, TRUE),

  -- FROZEN FOOD (10)
  ('FOOD-FRZ-000001', '8902001004001', 'Frozen Mixed Vegetables', 'Safal', 'Frozen Food', 'Vegetables', 'IQF mixed vegetables', 'g', '500 g', 95.00, 72.00, 90.00, 5.00, TRUE),
  ('FOOD-FRZ-000002', '8902001004002', 'Frozen Green Peas', 'Safal', 'Frozen Food', 'Vegetables', 'IQF green peas', 'g', '500 g', 80.00, 60.00, 75.00, 5.00, TRUE),
  ('FOOD-FRZ-000003', '8902001004003', 'Frozen Sweet Corn', 'Safal', 'Frozen Food', 'Vegetables', 'IQF sweet corn kernels', 'g', '500 g', 85.00, 64.00, 80.00, 5.00, TRUE),
  ('FOOD-FRZ-000004', '8902001004004', 'Frozen French Fries', 'McCain', 'Frozen Food', 'Snacks', 'Crispy French fries', 'g', '750 g', 190.00, 148.00, 180.00, 12.00, TRUE),
  ('FOOD-FRZ-000005', '8902001004005', 'Frozen Aloo Tikki', 'McCain', 'Frozen Food', 'Snacks', 'Ready to fry aloo tikki', 'g', '400 g', 145.00, 112.00, 138.00, 12.00, TRUE),
  ('FOOD-FRZ-000006', '8902001004006', 'Frozen Samosa', 'ITC Master Chef', 'Frozen Food', 'Snacks', 'Aloo samosa, 15 pcs', 'pack', '600 g', 180.00, 140.00, 170.00, 12.00, TRUE),
  ('FOOD-FRZ-000007', '8902001004007', 'Frozen Paratha', 'McCain', 'Frozen Food', 'Bread', 'Multi-layered aloo paratha', 'pack', '4 pcs (400 g)', 110.00, 85.00, 104.00, 5.00, TRUE),
  ('FOOD-FRZ-000008', '8902001004008', 'Frozen Pizza Base', 'Dr. Oetker', 'Frozen Food', 'Bread', 'Thin crust pizza base', 'pack', '2 pcs', 130.00, 100.00, 122.00, 12.00, TRUE),
  ('FOOD-FRZ-000009', '8902001004009', 'Frozen Fish Fingers', 'ITC Master Chef', 'Frozen Food', 'Seafood', 'Breaded fish fingers', 'g', '300 g', 250.00, 195.00, 237.00, 5.00, TRUE),
  ('FOOD-FRZ-000010', '8902001004010', 'Ice Cream Vanilla Tub', 'Amul', 'Frozen Food', 'Ice Cream', 'Real milk vanilla ice cream', 'ml', '1 L', 250.00, 195.00, 237.00, 18.00, TRUE),

  -- BAKERY (10)
  ('FOOD-BKRY-000001', '8902001005001', 'White Bread Loaf', 'Britannia', 'Bakery', 'Bread', 'Soft white sandwich bread', 'pack', '400 g', 40.00, 30.00, 37.00, 0.00, TRUE),
  ('FOOD-BKRY-000002', '8902001005002', 'Whole Wheat Bread', 'Britannia', 'Bakery', 'Bread', 'Whole wheat brown bread', 'pack', '400 g', 50.00, 38.00, 47.00, 0.00, TRUE),
  ('FOOD-BKRY-000003', '8902001005003', 'Multigrain Bread', 'Harvest Gold', 'Bakery', 'Bread', 'Multigrain bread with seeds', 'pack', '450 g', 65.00, 50.00, 62.00, 0.00, TRUE),
  ('FOOD-BKRY-000004', '8902001005004', 'Pav Bun', 'Britannia', 'Bakery', 'Buns', 'Soft dinner pav bun', 'pack', '6 pcs', 30.00, 22.00, 28.00, 0.00, TRUE),
  ('FOOD-BKRY-000005', '8902001005005', 'Burger Buns', 'Harvest Gold', 'Bakery', 'Buns', 'Sesame burger buns', 'pack', '4 pcs', 55.00, 42.00, 52.00, 0.00, TRUE),
  ('FOOD-BKRY-000006', '8902001005006', 'Cake Rusk', 'Britannia', 'Bakery', 'Rusk', 'Crunchy toast rusk', 'g', '300 g', 60.00, 46.00, 56.00, 18.00, TRUE),
  ('FOOD-BKRY-000007', '8902001005007', 'Fruit Cake Plum', 'Britannia', 'Bakery', 'Cake', 'Rich plum fruit cake', 'g', '250 g', 150.00, 115.00, 142.00, 18.00, TRUE),
  ('FOOD-BKRY-000008', '8902001005008', 'Croissant Butter', 'Modern', 'Bakery', 'Pastry', 'All-butter croissants', 'pack', '3 pcs', 120.00, 92.00, 112.00, 18.00, TRUE),
  ('FOOD-BKRY-000009', '8902001005009', 'Nan Bread Pack', 'Taza', 'Bakery', 'Bread', 'Tandoori naan ready to heat', 'pack', '5 pcs', 80.00, 62.00, 75.00, 5.00, TRUE),
  ('FOOD-BKRY-000010', '8902001005010', 'Khakhra Masala', 'Induben', 'Bakery', 'Flatbread', 'Crispy masala khakhra', 'g', '200 g', 60.00, 46.00, 56.00, 5.00, TRUE),

  -- BEVERAGES (10)
  ('FOOD-BVGR-000001', '8902001006001', 'Fresh Orange Juice', 'Tropicana', 'Beverages', 'Juice', 'Not from concentrate orange juice', 'ml', '1 L', 130.00, 100.00, 122.00, 12.00, TRUE),
  ('FOOD-BVGR-000002', '8902001006002', 'Coconut Water Pack', 'Paper Boat', 'Beverages', 'Juice', 'Tender coconut water', 'ml', '200 ml', 30.00, 22.00, 28.00, 12.00, TRUE),
  ('FOOD-BVGR-000003', '8902001006003', 'Aam Panna Drink', 'Paper Boat', 'Beverages', 'Traditional', 'Raw mango drink', 'ml', '200 ml', 25.00, 18.00, 23.00, 12.00, TRUE),
  ('FOOD-BVGR-000004', '8902001006004', 'Green Tea Tulsi', 'Organic India', 'Beverages', 'Tea', 'Organic tulsi green tea bags', 'pack', '25 bags', 165.00, 128.00, 155.00, 5.00, TRUE),
  ('FOOD-BVGR-000005', '8902001006005', 'Cold Brew Coffee', 'Sleepy Owl', 'Beverages', 'Coffee', 'Ready to drink cold brew', 'ml', '200 ml', 90.00, 68.00, 85.00, 18.00, TRUE),
  ('FOOD-BVGR-000006', '8902001006006', 'Lassi Sweet Mango', 'Amul', 'Beverages', 'Dairy Drink', 'Thick mango lassi', 'ml', '200 ml', 25.00, 18.00, 23.00, 0.00, TRUE),
  ('FOOD-BVGR-000007', '8902001006007', 'Buttermilk Masala', 'Amul', 'Beverages', 'Dairy Drink', 'Spiced buttermilk chaas', 'ml', '200 ml', 20.00, 14.00, 18.00, 0.00, TRUE),
  ('FOOD-BVGR-000008', '8902001006008', 'Protein Shake Chocolate', 'Amul', 'Beverages', 'Health Drink', 'High protein milk shake', 'ml', '200 ml', 50.00, 38.00, 47.00, 12.00, TRUE),
  ('FOOD-BVGR-000009', '8902001006009', 'Nimbu Pani (Lemon Water)', 'Paper Boat', 'Beverages', 'Traditional', 'Traditional lemonade drink', 'ml', '200 ml', 25.00, 18.00, 23.00, 12.00, TRUE),
  ('FOOD-BVGR-000010', '8902001006010', 'Kombucha Original', 'Atmosphere', 'Beverages', 'Probiotic', 'Fermented probiotic tea', 'ml', '250 ml', 150.00, 115.00, 142.00, 18.00, TRUE),

  -- DAIRY (10)
  ('FOOD-DARY-000001', '8902001007001', 'Fresh Paneer Block', 'Amul', 'Dairy', 'Paneer', 'Fresh cottage cheese for cooking', 'g', '500 g', 210.00, 168.00, 200.00, 0.00, TRUE),
  ('FOOD-DARY-000002', '8902001007002', 'Greek Yogurt Natural', 'Epigamia', 'Dairy', 'Yogurt', 'Thick strained greek yogurt', 'g', '90 g', 45.00, 34.00, 42.00, 12.00, TRUE),
  ('FOOD-DARY-000003', '8902001007003', 'Mozzarella Cheese Block', 'Amul', 'Dairy', 'Cheese', 'Pizza mozzarella cheese', 'g', '200 g', 135.00, 105.00, 128.00, 12.00, TRUE),
  ('FOOD-DARY-000004', '8902001007004', 'Cream Cheese Spread', 'Britannia', 'Dairy', 'Cheese', 'Smooth cream cheese spread', 'g', '180 g', 110.00, 85.00, 104.00, 12.00, TRUE),
  ('FOOD-DARY-000005', '8902001007005', 'Shrikhand Kesar', 'Amul', 'Dairy', 'Dessert', 'Saffron flavoured shrikhand', 'g', '500 g', 190.00, 148.00, 180.00, 12.00, TRUE),
  ('FOOD-DARY-000006', '8902001007006', 'A2 Cow Milk', 'Sid''s Farm', 'Dairy', 'Milk', 'Farm fresh A2 cow milk', 'ml', '500 ml', 42.00, 34.00, 40.00, 0.00, TRUE),
  ('FOOD-DARY-000007', '8902001007007', 'Flavoured Yogurt Strawberry', 'Epigamia', 'Dairy', 'Yogurt', 'Strawberry fruit yogurt', 'g', '90 g', 35.00, 26.00, 33.00, 12.00, TRUE),
  ('FOOD-DARY-000008', '8902001007008', 'Toned Milk Tetra Pack', 'Amul', 'Dairy', 'Milk', 'UHT toned milk, shelf stable', 'ml', '1 L', 68.00, 55.00, 65.00, 0.00, TRUE),
  ('FOOD-DARY-000009', '8902001007009', 'Butter Unsalted Block', 'Amul', 'Dairy', 'Butter', 'Unsalted white butter', 'g', '500 g', 270.00, 220.00, 257.00, 12.00, TRUE),
  ('FOOD-DARY-000010', '8902001007010', 'Mishti Doi (Sweet Curd)', 'Mother Dairy', 'Dairy', 'Dessert', 'Bengali style sweet curd', 'g', '85 g', 25.00, 18.00, 23.00, 0.00, TRUE),

  -- FRUITS & VEGETABLES (10)
  ('FOOD-FRUT-000001', '8902001008001', 'Bananas (Robusta)', 'Farm Fresh', 'Produce', 'Fruits', 'Ripe robusta bananas', 'dozen', '1 dozen', 50.00, 35.00, 47.00, 0.00, TRUE),
  ('FOOD-FRUT-000002', '8902001008002', 'Apple Red Delicious', 'Kashmiri', 'Produce', 'Fruits', 'Premium Kashmir apples', 'kg', '1 kg', 180.00, 140.00, 170.00, 0.00, TRUE),
  ('FOOD-FRUT-000003', '8902001008003', 'Mango Alphonso', 'Ratnagiri', 'Produce', 'Fruits', 'Hapus/Alphonso mango (seasonal)', 'dozen', '1 dozen', 800.00, 620.00, 760.00, 0.00, TRUE),
  ('FOOD-FRUT-000004', '8902001008004', 'Pomegranate (Anar)', 'Farm Fresh', 'Produce', 'Fruits', 'Fresh pomegranate', 'kg', '1 kg', 220.00, 170.00, 210.00, 0.00, TRUE),
  ('FOOD-FRUT-000005', '8902001008005', 'Papaya (Papita)', 'Farm Fresh', 'Produce', 'Fruits', 'Medium ripe papaya', 'kg', '1 kg', 60.00, 42.00, 55.00, 0.00, TRUE),
  ('FOOD-VEGG-000001', '8902001008006', 'Tomato (Tamatar)', 'Farm Fresh', 'Produce', 'Vegetables', 'Fresh firm tomatoes', 'kg', '1 kg', 40.00, 25.00, 37.00, 0.00, TRUE),
  ('FOOD-VEGG-000002', '8902001008007', 'Onion (Pyaaz)', 'Farm Fresh', 'Produce', 'Vegetables', 'Medium red onions', 'kg', '1 kg', 35.00, 22.00, 32.00, 0.00, TRUE),
  ('FOOD-VEGG-000003', '8902001008008', 'Potato (Aloo)', 'Farm Fresh', 'Produce', 'Vegetables', 'Medium potatoes', 'kg', '1 kg', 30.00, 18.00, 27.00, 0.00, TRUE),
  ('FOOD-VEGG-000004', '8902001008009', 'Green Chilli', 'Farm Fresh', 'Produce', 'Vegetables', 'Fresh green chillies', 'g', '250 g', 15.00, 8.00, 13.00, 0.00, TRUE),
  ('FOOD-VEGG-000005', '8902001008010', 'Coriander Leaves Fresh', 'Farm Fresh', 'Produce', 'Herbs', 'Fresh coriander/cilantro bunch', 'bunch', '1 bunch', 10.00, 5.00, 9.00, 0.00, TRUE),

  -- SNACKS (10)
  ('FOOD-SNCK-000001', '8902001009001', 'Samosa (Frozen 6-pack)', 'Haldiram', 'Snacks', 'Indian Snacks', 'Ready to fry vegetable samosas', 'pack', '6 pcs', 90.00, 68.00, 85.00, 12.00, TRUE),
  ('FOOD-SNCK-000002', '8902001009002', 'Dhokla Instant Mix', 'Gits', 'Snacks', 'Indian Snacks', 'Instant khaman dhokla mix', 'g', '200 g', 55.00, 42.00, 52.00, 18.00, TRUE),
  ('FOOD-SNCK-000003', '8902001009003', 'Vada Pav Frozen', 'ITC', 'Snacks', 'Indian Snacks', 'Ready to heat vada pav', 'pack', '4 pcs', 120.00, 92.00, 112.00, 12.00, TRUE),
  ('FOOD-SNCK-000004', '8902001009004', 'Masala Peanuts', 'Haldiram', 'Snacks', 'Namkeen', 'Spicy coated peanuts', 'g', '200 g', 55.00, 42.00, 52.00, 12.00, TRUE),
  ('FOOD-SNCK-000005', '8902001009005', 'Mixture Bombay Style', 'Haldiram', 'Snacks', 'Namkeen', 'Classic Bombay mix', 'g', '400 g', 130.00, 100.00, 122.00, 12.00, TRUE),
  ('FOOD-SNCK-000006', '8902001009006', 'Corn Nuts Roasted', 'Cornitos', 'Snacks', 'Western Snacks', 'Roasted corn kernels', 'g', '150 g', 60.00, 46.00, 56.00, 12.00, TRUE),
  ('FOOD-SNCK-000007', '8902001009007', 'Makhana (Fox Nuts) Roasted', 'True Elements', 'Snacks', 'Healthy Snacks', 'Himalayan pink salt makhana', 'g', '100 g', 120.00, 92.00, 112.00, 12.00, TRUE),
  ('FOOD-SNCK-000008', '8902001009008', 'Protein Bar Choco Fudge', 'RiteBite', 'Snacks', 'Healthy Snacks', 'High protein snack bar', 'bar', '70 g', 150.00, 115.00, 142.00, 18.00, TRUE),
  ('FOOD-SNCK-000009', '8902001009009', 'Khari Biscuit', 'Britannia', 'Snacks', 'Indian Snacks', 'Crispy puff pastry biscuit', 'g', '200 g', 45.00, 34.00, 42.00, 18.00, TRUE),
  ('FOOD-SNCK-000010', '8902001009010', 'Mathri Masala', 'Haldiram', 'Snacks', 'Indian Snacks', 'Traditional spiced mathri', 'g', '200 g', 65.00, 50.00, 62.00, 12.00, TRUE),

  -- MEAT & SEAFOOD (5)
  ('FOOD-MEAT-000001', '8902001010001', 'Chicken Breast Boneless', 'FreshToHome', 'Meat', 'Poultry', 'Fresh skinless boneless chicken breast', 'g', '500 g', 250.00, 195.00, 237.00, 0.00, TRUE),
  ('FOOD-MEAT-000002', '8902001010002', 'Mutton Curry Cut', 'Licious', 'Meat', 'Red Meat', 'Fresh goat meat curry pieces', 'g', '500 g', 550.00, 430.00, 522.00, 0.00, TRUE),
  ('FOOD-MEAT-000003', '8902001010003', 'Eggs Farm Fresh', 'Keggs', 'Meat', 'Eggs', 'Free range farm eggs', 'tray', '30 eggs', 250.00, 195.00, 237.00, 0.00, TRUE),
  ('FOOD-MEAT-000004', '8902001010004', 'Fish Pomfret Fresh', 'FreshToHome', 'Meat', 'Seafood', 'Fresh whole pomfret (cleaned)', 'g', '500 g', 450.00, 350.00, 427.00, 0.00, TRUE),
  ('FOOD-MEAT-000005', '8902001010005', 'Prawns Medium (Cleaned)', 'FreshToHome', 'Meat', 'Seafood', 'Cleaned medium prawns', 'g', '500 g', 500.00, 390.00, 475.00, 0.00, TRUE)

ON CONFLICT (sku) DO NOTHING;

-- Food product details for selected items
DO $$
DECLARE pid UUID;
BEGIN
  SELECT id INTO pid FROM food_master.products WHERE sku = 'FOOD-FRZ-000001';
  INSERT INTO food_master.food_product_details (product_id, food_type, storage_type, best_before_days, is_vegetarian) VALUES (pid, 'Frozen', 'Frozen', 365, TRUE) ON CONFLICT DO NOTHING;

  SELECT id INTO pid FROM food_master.products WHERE sku = 'FOOD-BKRY-000001';
  INSERT INTO food_master.food_product_details (product_id, food_type, storage_type, best_before_days, is_vegetarian) VALUES (pid, 'Bakery', 'Ambient', 5, TRUE) ON CONFLICT DO NOTHING;

  SELECT id INTO pid FROM food_master.products WHERE sku = 'FOOD-DARY-000001';
  INSERT INTO food_master.food_product_details (product_id, food_type, storage_type, best_before_days, is_vegetarian) VALUES (pid, 'Dairy', 'Chilled', 7, TRUE) ON CONFLICT DO NOTHING;

  SELECT id INTO pid FROM food_master.products WHERE sku = 'FOOD-MEAT-000001';
  INSERT INTO food_master.food_product_details (product_id, food_type, storage_type, best_before_days, is_vegetarian) VALUES (pid, 'Raw', 'Chilled', 2, FALSE) ON CONFLICT DO NOTHING;

  SELECT id INTO pid FROM food_master.products WHERE sku = 'FOOD-RTE-000001';
  INSERT INTO food_master.food_product_details (product_id, food_type, storage_type, best_before_days, is_vegetarian) VALUES (pid, 'Ready to Eat', 'Ambient', 365, TRUE) ON CONFLICT DO NOTHING;
END $$;
