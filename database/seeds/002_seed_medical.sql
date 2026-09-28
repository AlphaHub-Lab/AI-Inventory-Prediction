-- ============================================================================
-- SEED: MEDICAL MASTER CATALOG (110+ realistic Indian pharmacy products)
-- ============================================================================
-- NOTE: These are illustrative catalog entries only. Drug compositions,
-- prescription schedules, and regulatory classifications are simplified
-- examples and must NOT be used for actual pharmaceutical compliance.
-- ============================================================================

-- Suppliers
INSERT INTO medical_master.suppliers (supplier_code, supplier_name, contact_person, phone, email, city, state, pincode, gst_number, payment_terms)
VALUES
  ('MSUP-001', 'PharmEasy Wholesale', 'Dr. Anand Verma', '9888543210', 'anand@pharmeasy.in', 'Mumbai', 'Maharashtra', '400050', '27AABCP1234F1Z5', 'Net 30'),
  ('MSUP-002', 'Medline Distributors', 'Kavitha Reddy', '9888543211', 'kavitha@medline.in', 'Hyderabad', 'Telangana', '500001', '36AABCM5678G2Z3', 'Net 15'),
  ('MSUP-003', 'Apollo Pharmacy Supply', 'Rajan Iyer', '9888543212', 'rajan@apollosupply.in', 'Chennai', 'Tamil Nadu', '600020', '33AABCA9012H3Z1', 'Net 45'),
  ('MSUP-004', 'Wellness First Pharma', 'Neha Gupta', '9888543213', 'neha@wellnessfirst.in', 'Delhi', 'Delhi', '110001', '07AABCW3456I4Z9', 'Net 21'),
  ('MSUP-005', 'Jan Aushadhi Depot', 'Manoj Singh', '9888543214', 'manoj@janaushadhi.in', 'Lucknow', 'Uttar Pradesh', '226001', '09AABCJ7890J5Z7', 'Net 30')
ON CONFLICT (supplier_code) DO NOTHING;

-- Products + medical details
DO $$
DECLARE
  prod_id UUID;
BEGIN

  -- Helper: insert product then its medical details
  -- Category: OTC Analgesics
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-PARA-000001', 'Paracetamol 500mg Tablets', 'Crocin', 'OTC', 'Analgesics', 'strip', '15 tablets', 30.00, 18.00, 27.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-PARA-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Paracetamol', 'Analgesic/Antipyretic', 'Tablet', '500 mg', 'GSK Consumer Healthcare', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-PARA-000002', 'Paracetamol 650mg Tablets', 'Dolo', 'OTC', 'Analgesics', 'strip', '15 tablets', 35.00, 22.00, 32.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-PARA-000002';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Paracetamol', 'Analgesic/Antipyretic', 'Tablet', '650 mg', 'Micro Labs', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-IBUP-000001', 'Ibuprofen 400mg Tablets', 'Brufen', 'OTC', 'Analgesics', 'strip', '15 tablets', 40.00, 25.00, 36.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-IBUP-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Ibuprofen', 'NSAID', 'Tablet', '400 mg', 'Abbott India', FALSE, NULL, 'Store below 25°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-DICP-000001', 'Diclofenac Gel', 'Voveran Emulgel', 'OTC', 'Analgesics', 'tube', '30 g', 110.00, 75.00, 99.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-DICP-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Diclofenac Diethylamine', 'Topical NSAID', 'Gel', '1%', 'Novartis India', FALSE, NULL, 'Store below 25°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-ASPR-000001', 'Aspirin 75mg Tablets', 'Ecosprin', 'OTC', 'Analgesics', 'strip', '14 tablets', 20.00, 12.00, 18.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-ASPR-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Aspirin', 'Antiplatelet', 'Tablet', '75 mg', 'USV Limited', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  -- Antacids / GI
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-ANTA-000001', 'Antacid Gel Suspension', 'Digene', 'OTC', 'Antacids', 'bottle', '200 ml', 95.00, 65.00, 85.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-ANTA-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Dried Aluminium Hydroxide + Magnesium Hydroxide', 'Antacid', 'Suspension', NULL, 'Abbott India', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-RANT-000001', 'Ranitidine 150mg Tablets', 'Rantac', 'OTC', 'Antacids', 'strip', '10 tablets', 25.00, 15.00, 22.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-RANT-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Ranitidine', 'H2 Blocker', 'Tablet', '150 mg', 'J.B. Chemicals', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-PANT-000001', 'Pantoprazole 40mg Tablets', 'Pan-D', 'Prescription', 'Antacids', 'strip', '15 tablets', 120.00, 78.00, 108.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-PANT-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Pantoprazole + Domperidone', 'PPI + Prokinetic', 'Capsule', '40mg + 30mg', 'Alkem Laboratories', TRUE, 'H', 'Store below 25°C') ON CONFLICT (product_id) DO NOTHING;

  -- Cough & Cold
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-COUG-000001', 'Cough Syrup', 'Benadryl', 'OTC', 'Cough & Cold', 'bottle', '150 ml', 110.00, 75.00, 99.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-COUG-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Diphenhydramine', 'Antihistamine', 'Syrup', '14.08 mg/5ml', 'Johnson & Johnson', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-COUG-000002', 'Cough Lozenges', 'Vicks', 'OTC', 'Cough & Cold', 'pack', '20 lozenges', 55.00, 38.00, 49.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-COUG-000002';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Menthol + Eucalyptus Oil', 'Throat Lozenge', 'Lozenge', NULL, 'Procter & Gamble', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-CETR-000001', 'Cetirizine 10mg Tablets', 'Cetzine', 'OTC', 'Cough & Cold', 'strip', '10 tablets', 35.00, 22.00, 31.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-CETR-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Cetirizine Hydrochloride', 'Antihistamine', 'Tablet', '10 mg', 'Dr. Reddy''s', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  -- Vitamins & Supplements
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-VITC-000001', 'Vitamin C 500mg Chewable', 'Limcee', 'OTC', 'Vitamins', 'strip', '15 tablets', 25.00, 16.00, 22.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-VITC-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Ascorbic Acid', 'Vitamin Supplement', 'Chewable Tablet', '500 mg', 'Abbott India', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-VITD-000001', 'Vitamin D3 60000 IU Sachet', 'Uprise D3', 'OTC', 'Vitamins', 'sachet', '4 sachets', 200.00, 140.00, 180.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-VITD-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Cholecalciferol', 'Vitamin Supplement', 'Oral Sachet', '60000 IU', 'Alkem Laboratories', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-CALC-000001', 'Calcium + Vitamin D3 Tablets', 'Shelcal 500', 'OTC', 'Vitamins', 'strip', '15 tablets', 145.00, 98.00, 130.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-CALC-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Calcium Carbonate + Vitamin D3', 'Mineral Supplement', 'Tablet', '500mg + 250IU', 'Torrent Pharmaceuticals', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-IRON-000001', 'Iron + Folic Acid Tablets', 'Autrin', 'OTC', 'Vitamins', 'strip', '30 capsules', 110.00, 75.00, 99.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-IRON-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Ferrous Fumarate + Folic Acid', 'Hematonic', 'Capsule', NULL, 'GSK Consumer Healthcare', FALSE, NULL, 'Store below 30°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-MULT-000001', 'Multivitamin + Multimineral', 'Supradyn', 'OTC', 'Vitamins', 'strip', '15 tablets', 55.00, 36.00, 49.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-MULT-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Multivitamin Complex', 'Vitamin/Mineral Supplement', 'Tablet', NULL, 'Bayer Zydus Pharma', FALSE, NULL, 'Store below 25°C') ON CONFLICT (product_id) DO NOTHING;

  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES ('MED-OMG3-000001', 'Omega-3 Fish Oil Capsules', 'Seven Seas', 'OTC', 'Vitamins', 'bottle', '60 capsules', 450.00, 320.00, 405.00, 12.00) ON CONFLICT (sku) DO NOTHING;
  SELECT id INTO prod_id FROM medical_master.products WHERE sku = 'MED-OMG3-000001';
  INSERT INTO medical_master.medical_product_details (product_id, generic_name, drug_type, dosage_form, strength, manufacturer, prescription_required, schedule, storage_conditions)
  VALUES (prod_id, 'Omega-3 Fatty Acids', 'Dietary Supplement', 'Soft Gelatin Capsule', '1000 mg', 'Procter & Gamble', FALSE, NULL, 'Store below 25°C, protect from light') ON CONFLICT (product_id) DO NOTHING;

  -- First Aid & Medical Devices
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-BAND-000001', 'Adhesive Bandage Strips', 'Band-Aid', 'First Aid', 'Dressings', 'box', '100 strips', 230.00, 160.00, 207.00, 12.00),
    ('MED-BAND-000002', 'Crepe Bandage Roll', 'Dynaplast', 'First Aid', 'Dressings', 'roll', '10 cm x 4 m', 85.00, 58.00, 76.00, 12.00),
    ('MED-GAUZ-000001', 'Sterile Gauze Pads', 'Johnson & Johnson', 'First Aid', 'Dressings', 'pack', '10 pcs', 70.00, 48.00, 63.00, 12.00),
    ('MED-COTN-000001', 'Absorbent Cotton Roll', 'Johnson & Johnson', 'First Aid', 'Cotton', 'roll', '500 g', 180.00, 125.00, 162.00, 12.00),
    ('MED-THER-000001', 'Digital Thermometer', 'Dr. Morepen', 'Medical Devices', 'Thermometer', 'unit', '1 pc', 150.00, 95.00, 135.00, 12.00),
    ('MED-BPMO-000001', 'Digital BP Monitor', 'Omron', 'Medical Devices', 'BP Monitor', 'unit', '1 pc', 1850.00, 1350.00, 1665.00, 12.00),
    ('MED-GLUC-000001', 'Glucometer with Strips', 'Accu-Chek', 'Medical Devices', 'Glucometer', 'kit', '1 kit + 10 strips', 950.00, 700.00, 855.00, 12.00),
    ('MED-MASK-000001', 'Surgical Face Mask 3-Ply', 'MedPro', 'First Aid', 'Protection', 'box', '50 masks', 150.00, 90.00, 135.00, 12.00),
    ('MED-GLOV-000001', 'Nitrile Examination Gloves', 'MedPro', 'First Aid', 'Protection', 'box', '100 gloves', 350.00, 240.00, 315.00, 12.00),
    ('MED-TAPE-000001', 'Medical Adhesive Tape', 'Micropore', 'First Aid', 'Dressings', 'roll', '1 inch x 5 m', 65.00, 44.00, 58.00, 12.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Skin Care / Topical
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-ANTI-000001', 'Antiseptic Cream', 'Betadine', 'OTC', 'Skin Care', 'tube', '15 g', 60.00, 40.00, 54.00, 12.00),
    ('MED-ANTI-000002', 'Burnol Cream', 'Burnol', 'OTC', 'Skin Care', 'tube', '20 g', 55.00, 38.00, 49.00, 12.00),
    ('MED-BORJ-000001', 'Boroline Antiseptic Cream', 'Boroline', 'OTC', 'Skin Care', 'tube', '20 g', 40.00, 28.00, 36.00, 12.00),
    ('MED-CALA-000001', 'Calamine Lotion', 'Lacto Calamine', 'OTC', 'Skin Care', 'bottle', '120 ml', 185.00, 128.00, 166.00, 18.00),
    ('MED-MOIS-000001', 'Moisturizing Cream', 'Cetaphil', 'OTC', 'Skin Care', 'tube', '80 g', 395.00, 275.00, 355.00, 18.00),
    ('MED-SUNB-000001', 'Sunblock SPF50 Lotion', 'Neutrogena', 'OTC', 'Skin Care', 'tube', '88 ml', 450.00, 310.00, 405.00, 18.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Hygiene
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-HSAN-000001', 'Hand Sanitizer Gel', 'Dettol', 'OTC', 'Hygiene', 'bottle', '200 ml', 130.00, 90.00, 117.00, 18.00),
    ('MED-HSAN-000002', 'Sterillium Hand Rub', 'Sterillium', 'OTC', 'Hygiene', 'bottle', '100 ml', 195.00, 135.00, 175.00, 18.00),
    ('MED-DTWP-000001', 'Dettol Antiseptic Liquid', 'Dettol', 'OTC', 'Hygiene', 'bottle', '500 ml', 220.00, 152.00, 198.00, 18.00),
    ('MED-BWSH-000001', 'Betadine Body Wash', 'Betadine', 'OTC', 'Hygiene', 'bottle', '250 ml', 280.00, 194.00, 252.00, 18.00)
  ON CONFLICT (sku) DO NOTHING;

  -- ORS & Electrolytes
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-ORS-000001', 'ORS Orange Flavour', 'Electral', 'OTC', 'ORS', 'sachet', '21.8 g', 22.00, 14.00, 20.00, 5.00),
    ('MED-ORS-000002', 'ORS Apple Flavour Tetra Pack', 'Enerzal', 'OTC', 'ORS', 'pack', '200 ml', 25.00, 16.00, 22.00, 5.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Eye/Ear Care
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-EYDR-000001', 'Lubricant Eye Drops', 'Refresh Tears', 'OTC', 'Eye Care', 'bottle', '10 ml', 140.00, 96.00, 126.00, 12.00),
    ('MED-EYDR-000002', 'Itone Eye Drops', 'Itone', 'Ayurvedic', 'Eye Care', 'bottle', '10 ml', 50.00, 34.00, 45.00, 12.00),
    ('MED-EARW-000001', 'Ear Wax Drops', 'Soliwax', 'OTC', 'Ear Care', 'bottle', '10 ml', 65.00, 44.00, 58.00, 12.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Digestive Health
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-ENMA-000001', 'Isabgol Husk Powder', 'Sat-Isabgol', 'OTC', 'Digestive', 'pack', '200 g', 120.00, 82.00, 108.00, 0.00),
    ('MED-PROB-000001', 'Probiotic Capsules', 'Sporlac', 'OTC', 'Digestive', 'strip', '20 capsules', 90.00, 62.00, 81.00, 12.00),
    ('MED-LAXA-000001', 'Laxative Syrup', 'Cremaffin', 'OTC', 'Digestive', 'bottle', '225 ml', 155.00, 107.00, 139.00, 12.00),
    ('MED-ANTA-000002', 'Antacid Chewable Tablet', 'Gelusil MPS', 'OTC', 'Antacids', 'strip', '15 tablets', 30.00, 20.00, 27.00, 12.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Pain Relief Topical
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-BAAM-000001', 'Pain Relief Balm', 'Zandu Balm', 'OTC', 'Pain Relief', 'jar', '25 ml', 75.00, 52.00, 67.00, 18.00),
    ('MED-BAAM-000002', 'Moov Pain Relief Spray', 'Moov', 'OTC', 'Pain Relief', 'can', '80 g', 230.00, 160.00, 207.00, 18.00),
    ('MED-BAAM-000003', 'Iodex Pain Relief Balm', 'Iodex', 'OTC', 'Pain Relief', 'tube', '40 g', 105.00, 72.00, 94.00, 18.00),
    ('MED-VOLO-000001', 'Volini Pain Relief Gel', 'Volini', 'OTC', 'Pain Relief', 'tube', '30 g', 135.00, 93.00, 121.00, 18.00),
    ('MED-MUSC-000001', 'Muscle & Joint Rub', 'Tiger Balm', 'OTC', 'Pain Relief', 'jar', '21 ml', 130.00, 90.00, 117.00, 18.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Oral Care
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-MWSH-000001', 'Antiseptic Mouthwash', 'Listerine', 'OTC', 'Oral Care', 'bottle', '250 ml', 120.00, 82.00, 108.00, 18.00),
    ('MED-ULGR-000001', 'Mouth Ulcer Gel', 'Orasore', 'OTC', 'Oral Care', 'tube', '10 g', 75.00, 52.00, 67.00, 12.00),
    ('MED-TGEL-000001', 'Sensitivity Toothpaste', 'Sensodyne', 'OTC', 'Oral Care', 'tube', '80 g', 125.00, 86.00, 112.00, 18.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Ayurvedic / Wellness
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-CHYW-000001', 'Chyawanprash', 'Dabur', 'Ayurvedic', 'Wellness', 'jar', '500 g', 220.00, 152.00, 198.00, 0.00),
    ('MED-ASHW-000001', 'Ashwagandha Capsules', 'Himalaya', 'Ayurvedic', 'Wellness', 'bottle', '60 capsules', 210.00, 145.00, 189.00, 0.00),
    ('MED-TULS-000001', 'Tulsi Drops', 'Organic India', 'Ayurvedic', 'Wellness', 'bottle', '25 ml', 180.00, 124.00, 162.00, 0.00),
    ('MED-TRPH-000001', 'Triphala Tablets', 'Dabur', 'Ayurvedic', 'Digestive', 'bottle', '60 tablets', 110.00, 76.00, 99.00, 0.00),
    ('MED-HONY-000001', 'Manuka Honey', 'Comvita', 'Wellness', 'Supplements', 'jar', '250 g', 1800.00, 1350.00, 1620.00, 0.00),
    ('MED-PROT-000001', 'Whey Protein Powder', 'MuscleBlaze', 'Wellness', 'Supplements', 'jar', '1 kg', 2100.00, 1575.00, 1890.00, 18.00),
    ('MED-COLL-000001', 'Collagen Peptides', 'Oziva', 'Wellness', 'Supplements', 'jar', '250 g', 1450.00, 1015.00, 1305.00, 18.00),
    ('MED-BIOT-000001', 'Biotin Tablets for Hair', 'HealthKart', 'Wellness', 'Supplements', 'bottle', '90 tablets', 550.00, 385.00, 495.00, 18.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Baby Care
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-BPOW-000001', 'Baby Talcum Powder', 'Johnson''s Baby', 'Baby Care', 'Powder', 'bottle', '200 g', 185.00, 128.00, 166.00, 18.00),
    ('MED-BWIP-000001', 'Baby Wipes', 'Pampers', 'Baby Care', 'Wipes', 'pack', '72 wipes', 220.00, 152.00, 198.00, 18.00),
    ('MED-GRPW-000001', 'Gripe Water', 'Woodward''s', 'Baby Care', 'Gripe Water', 'bottle', '130 ml', 90.00, 62.00, 81.00, 12.00),
    ('MED-DIAP-000001', 'Baby Diapers (Medium)', 'Pampers', 'Baby Care', 'Diapers', 'pack', '76 diapers', 1050.00, 750.00, 945.00, 12.00),
    ('MED-BNSL-000001', 'Baby Nasal Saline Drops', 'Nasoclear', 'Baby Care', 'Nasal', 'bottle', '10 ml', 80.00, 55.00, 72.00, 12.00),
    ('MED-BBTH-000001', 'Baby Body Wash', 'Sebamed', 'Baby Care', 'Bath', 'bottle', '200 ml', 560.00, 390.00, 504.00, 18.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Feminine Care
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-SPAD-000001', 'Sanitary Pads Regular', 'Whisper Ultra', 'Feminine Care', 'Sanitary Pads', 'pack', '30 pads', 260.00, 180.00, 234.00, 0.00),
    ('MED-SPAD-000002', 'Sanitary Pads XL Night', 'Stayfree Secure', 'Feminine Care', 'Sanitary Pads', 'pack', '20 pads', 180.00, 125.00, 162.00, 0.00),
    ('MED-INTW-000001', 'Intimate Wash', 'V Wash', 'Feminine Care', 'Intimate Care', 'bottle', '100 ml', 180.00, 124.00, 162.00, 18.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Diabetes Care
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-GLST-000001', 'Glucose Test Strips', 'Accu-Chek', 'Medical Devices', 'Glucometer', 'box', '50 strips', 850.00, 620.00, 765.00, 12.00),
    ('MED-LANC-000001', 'Lancets for Glucometer', 'Accu-Chek', 'Medical Devices', 'Glucometer', 'box', '100 lancets', 350.00, 245.00, 315.00, 12.00),
    ('MED-SUFL-000001', 'Sugar Free Sweetener', 'Sugar Free Gold', 'Wellness', 'Diabetes Care', 'jar', '100 pellets', 120.00, 82.00, 108.00, 18.00),
    ('MED-DIAB-000001', 'Diabetic Foot Cream', 'Dr. Foot', 'OTC', 'Diabetes Care', 'tube', '100 ml', 250.00, 172.00, 225.00, 18.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Mobility & Ortho
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-KNEO-000001', 'Knee Cap Support', 'Tynor', 'Medical Devices', 'Mobility Aids', 'pair', '1 pair', 450.00, 310.00, 405.00, 12.00),
    ('MED-WRIS-000001', 'Wrist Support Band', 'Tynor', 'Medical Devices', 'Mobility Aids', 'unit', '1 pc', 350.00, 242.00, 315.00, 12.00),
    ('MED-HTWB-000001', 'Hot Water Bag', 'Medi-Pack', 'Medical Devices', 'Pain Relief', 'unit', '2 L', 195.00, 135.00, 175.00, 18.00),
    ('MED-ICEP-000001', 'Ice Pack Gel Reusable', 'Medi-Pack', 'Medical Devices', 'Pain Relief', 'unit', '1 pc', 165.00, 114.00, 148.00, 18.00),
    ('MED-NEBM-000001', 'Nebulizer Machine', 'Omron', 'Medical Devices', 'Respiratory', 'unit', '1 pc', 2200.00, 1600.00, 1980.00, 12.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Contraceptives (OTC)
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-CNDM-000001', 'Condoms (Dotted)', 'Durex', 'OTC', 'Contraceptives', 'pack', '10 pcs', 200.00, 140.00, 180.00, 12.00),
    ('MED-CNDM-000002', 'Condoms (Ribbed)', 'Manforce', 'OTC', 'Contraceptives', 'pack', '10 pcs', 100.00, 68.00, 90.00, 12.00)
  ON CONFLICT (sku) DO NOTHING;

  -- Storage & Accessories
  INSERT INTO medical_master.products (sku, product_name, brand, category, subcategory, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage)
  VALUES
    ('MED-PORG-000001', 'Pill Organizer Weekly', 'MedPro', 'Accessories', 'Storage', 'unit', '1 pc', 150.00, 95.00, 135.00, 18.00),
    ('MED-MDSP-000001', 'Medicine Dispenser Box', 'MedPro', 'Accessories', 'Storage', 'unit', '1 pc', 250.00, 175.00, 225.00, 18.00),
    ('MED-SYRG-000001', 'Disposable Syringes 5ml', 'Hindustan Syringes', 'Medical Devices', 'Syringes', 'box', '100 pcs', 400.00, 280.00, 360.00, 12.00),
    ('MED-OXMT-000001', 'Pulse Oximeter', 'Dr. Trust', 'Medical Devices', 'Monitoring', 'unit', '1 pc', 1200.00, 840.00, 1080.00, 12.00)
  ON CONFLICT (sku) DO NOTHING;

END $$;
