-- ============================================================================
-- SEED: STATIONERY MASTER CATALOG (110+ realistic Indian products)
-- ============================================================================

-- Suppliers
INSERT INTO stationery_master.suppliers (supplier_code, supplier_name, contact_person, phone, email, city, state, pincode, gst_number, payment_terms)
VALUES
  ('SSUP-001', 'Navneet Education Ltd.', 'Ramesh Bhatt', '9866543210', 'ramesh@navneet.in', 'Mumbai', 'Maharashtra', '400059', '27AABCN1234P1Z5', 'Net 30'),
  ('SSUP-002', 'Cello Stationery Hub', 'Priti Jain', '9866543211', 'priti@cello.in', 'Rajkot', 'Gujarat', '360001', '24AABCC5678Q2Z3', 'Net 15'),
  ('SSUP-003', 'Camlin Arts Distributors', 'Vijay Deshmukh', '9866543212', 'vijay@camlin.in', 'Mumbai', 'Maharashtra', '400051', '27AABCC9012R3Z1', 'Net 45'),
  ('SSUP-004', 'Office Mart Wholesale', 'Asha Krishnan', '9866543213', 'asha@officemart.in', 'Bangalore', 'Karnataka', '560001', '29AABCO3456S4Z9', 'Net 21'),
  ('SSUP-005', 'School Supply India', 'Dinesh Agarwal', '9866543214', 'dinesh@schoolsupply.in', 'Delhi', 'Delhi', '110002', '07AABCS7890T5Z7', 'Net 30')
ON CONFLICT (supplier_code) DO NOTHING;

-- Products
INSERT INTO stationery_master.products (sku, barcode, product_name, brand, category, subcategory, description, unit, pack_size, mrp, default_cost_price, default_selling_price, gst_percentage, is_active)
VALUES
  -- WRITING INSTRUMENTS (20)
  ('STA-BPEN-000001', '8901765001001', 'Ball Pen Blue (Pack of 10)', 'Cello Gripper', 'Writing', 'Ball Pen', 'Blue ink ball point pen with grip', 'pack', '10 pens', 80.00, 58.00, 74.00, 18.00, TRUE),
  ('STA-BPEN-000002', '8901765001002', 'Ball Pen Black', 'Reynolds 045', 'Writing', 'Ball Pen', 'Fine tip black ball pen', 'unit', '1 pen', 10.00, 7.00, 9.00, 18.00, TRUE),
  ('STA-BPEN-000003', '8901765001003', 'Ball Pen Red', 'Cello Gripper', 'Writing', 'Ball Pen', 'Red ink ball point pen', 'unit', '1 pen', 10.00, 7.00, 9.00, 18.00, TRUE),
  ('STA-GPEN-000001', '8901765001004', 'Gel Pen Blue 0.5mm', 'Pilot V5', 'Writing', 'Gel Pen', 'Extra fine gel ink pen', 'unit', '1 pen', 55.00, 40.00, 52.00, 18.00, TRUE),
  ('STA-GPEN-000002', '8901765001005', 'Gel Pen Black 0.7mm', 'Linc Pentonic', 'Writing', 'Gel Pen', 'Smooth writing gel pen', 'unit', '1 pen', 20.00, 14.00, 18.00, 18.00, TRUE),
  ('STA-GPEN-000003', '8901765001006', 'Gel Pen Multicolor Set', 'Cello Butterflow', 'Writing', 'Gel Pen', '10 colour gel pen set', 'pack', '10 pens', 150.00, 110.00, 142.00, 18.00, TRUE),
  ('STA-FPEN-000001', '8901765001007', 'Fountain Pen Classic', 'Parker Vector', 'Writing', 'Fountain Pen', 'Stainless steel fountain pen', 'unit', '1 pen', 350.00, 255.00, 330.00, 18.00, TRUE),
  ('STA-FPEN-000002', '8901765001008', 'Ink Cartridges Blue', 'Parker Quink', 'Writing', 'Pen Refills', 'Fountain pen ink cartridges', 'pack', '5 cartridges', 120.00, 88.00, 112.00, 18.00, TRUE),
  ('STA-PNCL-000001', '8901765001009', 'HB Pencil', 'Apsara Platinum', 'Writing', 'Pencil', 'Extra dark HB writing pencil', 'pack', '10 pencils', 50.00, 36.00, 47.00, 18.00, TRUE),
  ('STA-PNCL-000002', '8901765001010', '2B Drawing Pencil', 'Staedtler Noris', 'Writing', 'Pencil', 'Soft drawing pencil 2B grade', 'unit', '1 pencil', 25.00, 18.00, 23.00, 18.00, TRUE),
  ('STA-PNCL-000003', '8901765001011', 'Mechanical Pencil 0.5mm', 'Faber-Castell', 'Writing', 'Mechanical Pencil', 'Auto feed mechanical pencil', 'unit', '1 pencil', 60.00, 44.00, 56.00, 18.00, TRUE),
  ('STA-PNCL-000004', '8901765001012', 'Pencil Lead Refills 0.5mm', 'Faber-Castell', 'Writing', 'Pencil Refills', 'HB lead for mechanical pencil', 'tube', '12 leads', 20.00, 14.00, 18.00, 18.00, TRUE),
  ('STA-MARK-000001', '8901765001013', 'Permanent Marker Black', 'Camlin', 'Writing', 'Marker', 'Waterproof permanent marker', 'unit', '1 marker', 35.00, 25.00, 32.00, 18.00, TRUE),
  ('STA-MARK-000002', '8901765001014', 'Whiteboard Marker Set', 'Camlin', 'Writing', 'Marker', '4-colour whiteboard marker set', 'pack', '4 markers', 120.00, 88.00, 112.00, 18.00, TRUE),
  ('STA-HLTR-000001', '8901765001015', 'Highlighter Set', 'Luxor', 'Writing', 'Highlighter', 'Fluorescent highlighter 5-colour', 'pack', '5 highlighters', 100.00, 72.00, 94.00, 18.00, TRUE),
  ('STA-HLTR-000002', '8901765001016', 'Highlighter Yellow', 'Stabilo', 'Writing', 'Highlighter', 'Chisel tip yellow highlighter', 'unit', '1 highlighter', 45.00, 33.00, 42.00, 18.00, TRUE),
  ('STA-SKCH-000001', '8901765001017', 'Sketch Pen Set 12 Colours', 'Camlin', 'Writing', 'Sketch Pen', 'Washable sketch pen set for children', 'pack', '12 pens', 85.00, 62.00, 80.00, 18.00, TRUE),
  ('STA-SKCH-000002', '8901765001018', 'Sketch Pen Set 24 Colours', 'Faber-Castell', 'Writing', 'Sketch Pen', 'Fine tip connector pens', 'pack', '24 pens', 250.00, 182.00, 237.00, 18.00, TRUE),
  ('STA-CRYN-000001', '8901765001019', 'Wax Crayon Set 12', 'Camlin', 'Writing', 'Crayons', 'Non-toxic wax crayons', 'pack', '12 crayons', 40.00, 29.00, 37.00, 18.00, TRUE),
  ('STA-CRYN-000002', '8901765001020', 'Oil Pastel Set 25', 'Faber-Castell', 'Writing', 'Oil Pastels', 'Vibrant oil pastel colours', 'pack', '25 pastels', 180.00, 132.00, 170.00, 18.00, TRUE),

  -- PAPER & NOTEBOOKS (20)
  ('STA-NTBK-000001', '8901765002001', 'Single Line Notebook 200 Pages', 'Classmate', 'Notebooks', 'Ruled Notebook', 'Long single line ruled notebook', 'unit', '200 pages', 65.00, 48.00, 62.00, 12.00, TRUE),
  ('STA-NTBK-000002', '8901765002002', 'Four Line Notebook 172 Pages', 'Classmate', 'Notebooks', 'Ruled Notebook', 'Four line English notebook', 'unit', '172 pages', 50.00, 36.00, 47.00, 12.00, TRUE),
  ('STA-NTBK-000003', '8901765002003', 'Graph Notebook Square Ruled', 'Classmate', 'Notebooks', 'Graph Notebook', 'Square ruled graph notebook', 'unit', '172 pages', 55.00, 40.00, 52.00, 12.00, TRUE),
  ('STA-NTBK-000004', '8901765002004', 'Drawing Book A4', 'Navneet', 'Notebooks', 'Drawing Book', 'Unruled A4 drawing book', 'unit', '36 pages', 45.00, 33.00, 42.00, 12.00, TRUE),
  ('STA-NTBK-000005', '8901765002005', 'Spiral Notebook A5', 'Luxor', 'Notebooks', 'Spiral Notebook', 'A5 spiral bound notebook', 'unit', '160 pages', 75.00, 55.00, 70.00, 12.00, TRUE),
  ('STA-NTBK-000006', '8901765002006', 'Composition Notebook Hard Bound', 'Navneet', 'Notebooks', 'Composition Book', 'Premium hard cover notebook', 'unit', '200 pages', 95.00, 70.00, 90.00, 12.00, TRUE),
  ('STA-RGST-000001', '8901765002007', 'Long Register 400 Pages', 'Classmate', 'Notebooks', 'Register', 'A4 ruled long register', 'unit', '400 pages', 120.00, 88.00, 112.00, 12.00, TRUE),
  ('STA-RGST-000002', '8901765002008', 'Cash Memo Book', 'Navneet', 'Notebooks', 'Register', 'Carbon less cash memo pad', 'unit', '100 sets', 65.00, 48.00, 62.00, 12.00, TRUE),
  ('STA-PAPR-000001', '8901765002009', 'A4 Copier Paper 500 Sheets', 'JK Copier', 'Paper', 'Print Paper', '75 GSM white copier paper ream', 'ream', '500 sheets', 350.00, 275.00, 330.00, 18.00, TRUE),
  ('STA-PAPR-000002', '8901765002010', 'A4 Copier Paper Premium', 'JK Easy', 'Paper', 'Print Paper', '70 GSM everyday printing paper', 'ream', '500 sheets', 310.00, 245.00, 295.00, 18.00, TRUE),
  ('STA-PAPR-000003', '8901765002011', 'A3 Drawing Paper', 'Navneet', 'Paper', 'Art Paper', 'A3 cartridge paper for art', 'pack', '20 sheets', 120.00, 88.00, 112.00, 18.00, TRUE),
  ('STA-PAPR-000004', '8901765002012', 'Chart Paper (Assorted Colours)', 'Navneet', 'Paper', 'Art Paper', 'Full size colour chart paper', 'pack', '10 sheets', 50.00, 36.00, 47.00, 18.00, TRUE),
  ('STA-PAPR-000005', '8901765002013', 'Tracing Paper A4', 'Navneet', 'Paper', 'Specialty Paper', 'Transparent tracing paper', 'pack', '20 sheets', 60.00, 44.00, 56.00, 18.00, TRUE),
  ('STA-ENVL-000001', '8901765002014', 'White Envelope A4', 'JK', 'Paper', 'Envelopes', 'A4 white gummed envelope', 'pack', '25 envelopes', 55.00, 40.00, 52.00, 18.00, TRUE),
  ('STA-ENVL-000002', '8901765002015', 'Brown Envelope Legal', 'JK', 'Paper', 'Envelopes', 'Legal size brown kraft envelope', 'pack', '25 envelopes', 45.00, 33.00, 42.00, 18.00, TRUE),
  ('STA-STKY-000001', '8901765002016', 'Sticky Notes 3x3 Neon', 'Oddy', 'Paper', 'Sticky Notes', 'Neon colour sticky notes pad', 'pack', '100 sheets', 35.00, 25.00, 32.00, 18.00, TRUE),
  ('STA-STKY-000002', '8901765002017', 'Page Marker Flags', 'Oddy', 'Paper', 'Sticky Notes', 'Neon page marker flag set', 'pack', '5 colours x 25', 40.00, 29.00, 37.00, 18.00, TRUE),
  ('STA-DIRY-000001', '8901765002018', 'Daily Diary 2026', 'Nescafe/Classmate', 'Notebooks', 'Diary', 'One page per day diary', 'unit', '365 pages', 250.00, 185.00, 237.00, 12.00, TRUE),
  ('STA-LPAD-000001', '8901765002019', 'Legal Pad Yellow Ruled', 'Oddy', 'Paper', 'Legal Pad', 'US legal ruled writing pad', 'unit', '100 sheets', 80.00, 58.00, 75.00, 18.00, TRUE),
  ('STA-BNDR-000001', '8901765002020', 'Lab Record Book', 'Classmate', 'Notebooks', 'Lab Book', 'Science lab practical record', 'unit', '140 pages', 65.00, 48.00, 62.00, 12.00, TRUE),

  -- FILES & FOLDERS (12)
  ('STA-FILE-000001', '8901765003001', 'Spring File A4', 'Worldone', 'Files', 'Spring File', 'Board lever arch file', 'unit', '1 file', 45.00, 33.00, 42.00, 18.00, TRUE),
  ('STA-FILE-000002', '8901765003002', 'Box File Broad', 'Worldone', 'Files', 'Box File', 'Broad spine box file', 'unit', '1 file', 90.00, 66.00, 85.00, 18.00, TRUE),
  ('STA-FILE-000003', '8901765003003', 'Ring Binder 2D A4', 'Worldone', 'Files', 'Ring Binder', '2 D-ring binder folder', 'unit', '1 binder', 85.00, 62.00, 80.00, 18.00, TRUE),
  ('STA-FLDR-000001', '8901765003004', 'Clear Folder 20 Pockets', 'Solo', 'Files', 'Display Book', 'Clear display book 20 pockets', 'unit', '1 folder', 95.00, 70.00, 90.00, 18.00, TRUE),
  ('STA-FLDR-000002', '8901765003005', 'L-Shape Folder (Pack of 10)', 'Worldone', 'Files', 'L-Folder', 'Transparent L-shape document folder', 'pack', '10 folders', 65.00, 48.00, 62.00, 18.00, TRUE),
  ('STA-FLDR-000003', '8901765003006', 'Document Envelope Snap Button', 'Solo', 'Files', 'Document Bag', 'A4 button document bag', 'unit', '1 bag', 35.00, 25.00, 32.00, 18.00, TRUE),
  ('STA-FLDR-000004', '8901765003007', 'Expanding File 13 Pockets', 'Solo', 'Files', 'Expanding File', 'A4 accordion expanding file', 'unit', '1 file', 180.00, 132.00, 170.00, 18.00, TRUE),
  ('STA-CLIP-000001', '8901765003008', 'Clipboard A4 Wooden', 'Exam Board', 'Files', 'Clipboard', 'Writing clipboard exam board', 'unit', '1 board', 60.00, 44.00, 56.00, 18.00, TRUE),
  ('STA-SHTE-000001', '8901765003009', 'Sheet Protectors A4 (50 Pack)', 'Worldone', 'Files', 'Accessories', 'Clear A4 sheet protector pockets', 'pack', '50 sheets', 120.00, 88.00, 112.00, 18.00, TRUE),
  ('STA-TABF-000001', '8901765003010', 'Tab File Separator Set', 'Solo', 'Files', 'Accessories', 'A4 coloured tab divider set', 'pack', '12 tabs', 65.00, 48.00, 62.00, 18.00, TRUE),
  ('STA-PRFL-000001', '8901765003011', 'Project File Folder', 'Classmate', 'Files', 'Project File', 'School/college project file', 'unit', '1 file', 25.00, 18.00, 23.00, 18.00, TRUE),
  ('STA-CRTF-000001', '8901765003012', 'Certificate File Leather', 'Solo', 'Files', 'Certificate Holder', 'Premium leather look certificate holder', 'unit', '1 holder', 250.00, 185.00, 237.00, 18.00, TRUE),

  -- ADHESIVES & CUTTING (10)
  ('STA-GLUE-000001', '8901765004001', 'Glue Stick 15g', 'Fevicol MR', 'Adhesives', 'Glue Stick', 'Non-toxic glue stick', 'unit', '15 g', 25.00, 18.00, 23.00, 18.00, TRUE),
  ('STA-GLUE-000002', '8901765004002', 'White Glue Bottle', 'Fevicol MR', 'Adhesives', 'Liquid Glue', 'PVA white adhesive craft glue', 'bottle', '200 ml', 75.00, 55.00, 70.00, 18.00, TRUE),
  ('STA-GLUE-000003', '8901765004003', 'Super Glue (Instant)', 'Fevi Kwik', 'Adhesives', 'Super Glue', 'Cyanoacrylate instant adhesive', 'unit', '3 g', 30.00, 22.00, 28.00, 18.00, TRUE),
  ('STA-TAPE-000001', '8901765004004', 'Clear Tape Roll', 'Cello', 'Adhesives', 'Tape', 'Transparent adhesive tape', 'roll', '18mm x 33m', 25.00, 18.00, 23.00, 18.00, TRUE),
  ('STA-TAPE-000002', '8901765004005', 'Masking Tape', 'Oddy', 'Adhesives', 'Tape', 'General purpose masking tape', 'roll', '24mm x 20m', 55.00, 40.00, 52.00, 18.00, TRUE),
  ('STA-TAPE-000003', '8901765004006', 'Double-Sided Tape', 'Oddy', 'Adhesives', 'Tape', 'Double sided mounting tape', 'roll', '12mm x 5m', 45.00, 33.00, 42.00, 18.00, TRUE),
  ('STA-SCSR-000001', '8901765004007', 'Safety Scissors Kids', 'Faber-Castell', 'Cutting', 'Scissors', 'Round tip safety scissors', 'unit', '1 pair', 55.00, 40.00, 52.00, 18.00, TRUE),
  ('STA-SCSR-000002', '8901765004008', 'Office Scissors Stainless', 'Kangaro', 'Cutting', 'Scissors', '8 inch stainless steel scissors', 'unit', '1 pair', 85.00, 62.00, 80.00, 18.00, TRUE),
  ('STA-CUTR-000001', '8901765004009', 'Paper Cutter Knife', 'Kangaro', 'Cutting', 'Cutter', 'Retractable blade paper cutter', 'unit', '1 cutter', 30.00, 22.00, 28.00, 18.00, TRUE),
  ('STA-RPCH-000001', '8901765004010', 'Single Hole Punch', 'Kangaro', 'Cutting', 'Punch', 'Heavy duty single hole punch', 'unit', '1 punch', 65.00, 48.00, 62.00, 18.00, TRUE),

  -- ERASERS & SHARPENERS (6)
  ('STA-ERSR-000001', '8901765005001', 'Dust Free Eraser', 'Apsara Non-Dust', 'Erasers', 'Eraser', 'Non-dust white eraser', 'unit', '1 eraser', 10.00, 7.00, 9.00, 18.00, TRUE),
  ('STA-ERSR-000002', '8901765005002', 'Ink & Pencil Eraser', 'Pelican', 'Erasers', 'Eraser', 'Dual ink and pencil eraser', 'unit', '1 eraser', 15.00, 11.00, 14.00, 18.00, TRUE),
  ('STA-ERSR-000003', '8901765005003', 'Kneaded Art Eraser', 'Staedtler', 'Erasers', 'Art Eraser', 'Moldable kneaded eraser for charcoal', 'unit', '1 eraser', 45.00, 33.00, 42.00, 18.00, TRUE),
  ('STA-SHRP-000001', '8901765005004', 'Single Hole Sharpener', 'Apsara', 'Erasers', 'Sharpener', 'Metallic single hole sharpener', 'unit', '1 sharpener', 5.00, 3.00, 4.00, 18.00, TRUE),
  ('STA-SHRP-000002', '8901765005005', 'Double Hole Sharpener', 'Faber-Castell', 'Erasers', 'Sharpener', 'Two hole with container sharpener', 'unit', '1 sharpener', 30.00, 22.00, 28.00, 18.00, TRUE),
  ('STA-SHRP-000003', '8901765005006', 'Electric Pencil Sharpener', 'Kangaro', 'Erasers', 'Sharpener', 'Battery operated pencil sharpener', 'unit', '1 sharpener', 350.00, 255.00, 330.00, 18.00, TRUE),

  -- OFFICE SUPPLIES (15)
  ('STA-STPL-000001', '8901765006001', 'Desk Stapler No.10', 'Kangaro', 'Office Supplies', 'Stapler', 'Full strip metal stapler', 'unit', '1 stapler', 120.00, 88.00, 112.00, 18.00, TRUE),
  ('STA-STPL-000002', '8901765006002', 'Heavy Duty Stapler No.24/6', 'Kangaro', 'Office Supplies', 'Stapler', 'Heavy duty 40 sheet stapler', 'unit', '1 stapler', 350.00, 255.00, 330.00, 18.00, TRUE),
  ('STA-STPN-000001', '8901765006003', 'Stapler Pins No.10', 'Kangaro', 'Office Supplies', 'Staple Pins', 'Standard stapler pins box', 'box', '1000 pins', 15.00, 10.00, 13.00, 18.00, TRUE),
  ('STA-STPN-000002', '8901765006004', 'Stapler Pins No.24/6', 'Kangaro', 'Office Supplies', 'Staple Pins', 'Heavy duty staple pins', 'box', '1000 pins', 25.00, 18.00, 23.00, 18.00, TRUE),
  ('STA-RMVR-000001', '8901765006005', 'Staple Remover', 'Kangaro', 'Office Supplies', 'Staple Remover', 'Claw style staple remover', 'unit', '1 remover', 35.00, 25.00, 32.00, 18.00, TRUE),
  ('STA-PCLP-000001', '8901765006006', 'Paper Clips Gem (Pack of 100)', 'Kangaro', 'Office Supplies', 'Paper Clips', 'Standard gem paper clips', 'box', '100 clips', 20.00, 14.00, 18.00, 18.00, TRUE),
  ('STA-BCLP-000001', '8901765006007', 'Binder Clips 25mm (Pack of 12)', 'Kangaro', 'Office Supplies', 'Binder Clips', 'Black metal binder clips', 'box', '12 clips', 35.00, 25.00, 32.00, 18.00, TRUE),
  ('STA-PINS-000001', '8901765006008', 'Push Pins (Pack of 100)', 'Office Aid', 'Office Supplies', 'Push Pins', 'Coloured plastic head push pins', 'box', '100 pins', 30.00, 22.00, 28.00, 18.00, TRUE),
  ('STA-RUBR-000001', '8901765006009', 'Rubber Bands (100g)', 'Normal', 'Office Supplies', 'Rubber Bands', 'Assorted rubber bands', 'pack', '100 g', 25.00, 18.00, 23.00, 18.00, TRUE),
  ('STA-CALC-000001', '8901765006010', 'Scientific Calculator', 'Casio FX-991EX', 'Office Supplies', 'Calculator', '552 functions scientific calculator', 'unit', '1 calculator', 1350.00, 985.00, 1282.00, 18.00, TRUE),
  ('STA-CALC-000002', '8901765006011', 'Basic Calculator 12 Digit', 'Casio MJ-12Da', 'Office Supplies', 'Calculator', '12 digit desktop calculator', 'unit', '1 calculator', 595.00, 435.00, 565.00, 18.00, TRUE),
  ('STA-RLRR-000001', '8901765006012', 'Steel Ruler 30cm', 'Camlin', 'Office Supplies', 'Ruler', 'Stainless steel straight ruler', 'unit', '30 cm', 35.00, 25.00, 32.00, 18.00, TRUE),
  ('STA-RLRR-000002', '8901765006013', 'Plastic Ruler 15cm', 'Apsara', 'Office Supplies', 'Ruler', 'Transparent plastic ruler', 'unit', '15 cm', 10.00, 7.00, 9.00, 18.00, TRUE),
  ('STA-SCLE-000001', '8901765006014', 'Scale 30cm Architect', 'Rotring', 'Office Supplies', 'Scale', 'Triangular architect scale', 'unit', '30 cm', 180.00, 132.00, 170.00, 18.00, TRUE),
  ('STA-STRM-000001', '8901765006015', 'Letter Tray 3-Tier', 'Solo', 'Office Supplies', 'Desk Organizer', 'Plastic 3-tier document tray', 'unit', '1 set', 350.00, 255.00, 330.00, 18.00, TRUE),

  -- GEOMETRY & MATH (6)
  ('STA-GBOX-000001', '8901765007001', 'Geometry Box Full Set', 'Camlin Kokuyo', 'School Supplies', 'Geometry Box', 'Compass, divider, protractor, set squares', 'box', '1 box', 95.00, 70.00, 90.00, 18.00, TRUE),
  ('STA-GBOX-000002', '8901765007002', 'Compass Set Premium', 'Staedtler', 'School Supplies', 'Geometry Box', 'Metal compass with lead', 'unit', '1 set', 150.00, 110.00, 142.00, 18.00, TRUE),
  ('STA-PROT-000001', '8901765007003', 'Protractor 180°', 'Camlin', 'School Supplies', 'Geometry', 'Transparent protractor', 'unit', '1 protractor', 15.00, 11.00, 14.00, 18.00, TRUE),
  ('STA-STSQ-000001', '8901765007004', 'Set Square Pair 45/60', 'Apsara', 'School Supplies', 'Geometry', 'Pair of set squares transparent', 'pair', '2 pcs', 25.00, 18.00, 23.00, 18.00, TRUE),
  ('STA-ABED-000001', '8901765007005', 'Abacus Counting Frame', 'Educational Toys', 'School Supplies', 'Math Aids', 'Colourful counting abacus', 'unit', '1 abacus', 120.00, 88.00, 112.00, 18.00, TRUE),
  ('STA-DSKS-000001', '8901765007006', 'Drawing Board T-Square', 'Rotring', 'School Supplies', 'Drawing Tools', 'A3 portable drawing board', 'unit', '1 board', 480.00, 350.00, 455.00, 18.00, TRUE),

  -- ART SUPPLIES (10)
  ('STA-WCOL-000001', '8901765008001', 'Watercolour Cake Set 24', 'Camel', 'Art Supplies', 'Watercolour', '24 shade watercolour cake box', 'box', '24 shades', 180.00, 132.00, 170.00, 18.00, TRUE),
  ('STA-WCOL-000002', '8901765008002', 'Watercolour Tube Set 12', 'Camel', 'Art Supplies', 'Watercolour', '12 colour tube watercolours', 'pack', '12 tubes', 250.00, 185.00, 237.00, 18.00, TRUE),
  ('STA-ACRL-000001', '8901765008003', 'Acrylic Paint Set 12', 'Camel', 'Art Supplies', 'Acrylic Paint', '12 colour acrylic paint tubes', 'pack', '12 tubes (20ml)', 350.00, 255.00, 330.00, 18.00, TRUE),
  ('STA-BRSH-000001', '8901765008004', 'Paint Brush Set Flat', 'Camlin', 'Art Supplies', 'Brushes', '7 flat brushes assorted sizes', 'pack', '7 brushes', 120.00, 88.00, 112.00, 18.00, TRUE),
  ('STA-BRSH-000002', '8901765008005', 'Paint Brush Set Round', 'Camlin', 'Art Supplies', 'Brushes', '7 round brushes for watercolour', 'pack', '7 brushes', 110.00, 80.00, 104.00, 18.00, TRUE),
  ('STA-PALT-000001', '8901765008006', 'Paint Palette Plastic', 'Camlin', 'Art Supplies', 'Palette', '6-well plastic mixing palette', 'unit', '1 palette', 25.00, 18.00, 23.00, 18.00, TRUE),
  ('STA-CANV-000001', '8901765008007', 'Canvas Board 12x16', 'Camlin', 'Art Supplies', 'Canvas', 'Primed canvas board for painting', 'unit', '12x16 inch', 180.00, 132.00, 170.00, 18.00, TRUE),
  ('STA-CLRP-000001', '8901765008008', 'Colour Pencils 24 Shades', 'Faber-Castell', 'Art Supplies', 'Colour Pencils', 'Long hexagonal colour pencils', 'box', '24 pencils', 200.00, 146.00, 190.00, 18.00, TRUE),
  ('STA-CLRP-000002', '8901765008009', 'Colour Pencils 12 Shades', 'Camlin', 'Art Supplies', 'Colour Pencils', 'Full size colour pencils', 'box', '12 pencils', 80.00, 58.00, 75.00, 18.00, TRUE),
  ('STA-CHKB-000001', '8901765008010', 'Chalk Set White (50 pcs)', 'Apsara', 'Art Supplies', 'Chalk', 'Dustless white chalk sticks', 'box', '50 pcs', 25.00, 18.00, 23.00, 18.00, TRUE),

  -- DESK ACCESSORIES (6)
  ('STA-PNHL-000001', '8901765009001', 'Pen Holder Stand', 'Solo', 'Desk Accessories', 'Pen Holder', 'Multi-compartment pen stand', 'unit', '1 stand', 120.00, 88.00, 112.00, 18.00, TRUE),
  ('STA-PNCS-000001', '8901765009002', 'Pencil Case Zipper', 'Classmate', 'Desk Accessories', 'Pencil Case', 'Fabric zipper pencil pouch', 'unit', '1 pouch', 80.00, 58.00, 75.00, 18.00, TRUE),
  ('STA-DKPD-000001', '8901765009003', 'Desk Pad Writing Mat', 'Solo', 'Desk Accessories', 'Desk Pad', 'Leatherette desk writing pad', 'unit', '1 pad', 250.00, 185.00, 237.00, 18.00, TRUE),
  ('STA-WHTB-000001', '8901765009004', 'Whiteboard 2x3 ft', 'Pragati', 'Desk Accessories', 'Whiteboard', 'Magnetic dry erase whiteboard', 'unit', '2x3 ft', 650.00, 475.00, 617.00, 18.00, TRUE),
  ('STA-LMNT-000001', '8901765009005', 'Lamination Pouch A4 (100 Pack)', 'Oddy', 'Desk Accessories', 'Lamination', 'A4 thermal lamination pouches', 'pack', '100 pcs', 350.00, 255.00, 330.00, 18.00, TRUE),
  ('STA-CRTG-000001', '8901765009006', 'Printer Ink Cartridge Black', 'HP 805', 'Printer Supplies', 'Cartridge', 'HP 805 black ink cartridge', 'unit', '1 cartridge', 750.00, 548.00, 712.00, 18.00, TRUE)

ON CONFLICT (sku) DO NOTHING;

-- Stationery product details for selected items
DO $$
DECLARE pid UUID;
BEGIN
  SELECT id INTO pid FROM stationery_master.products WHERE sku = 'STA-BPEN-000001';
  INSERT INTO stationery_master.stationery_product_details (product_id, color, size, material) VALUES (pid, 'Blue', 'Standard', 'Plastic') ON CONFLICT DO NOTHING;

  SELECT id INTO pid FROM stationery_master.products WHERE sku = 'STA-GPEN-000001';
  INSERT INTO stationery_master.stationery_product_details (product_id, color, size, material) VALUES (pid, 'Blue', '0.5mm', 'Plastic/Metal') ON CONFLICT DO NOTHING;

  SELECT id INTO pid FROM stationery_master.products WHERE sku = 'STA-FPEN-000001';
  INSERT INTO stationery_master.stationery_product_details (product_id, color, size, material) VALUES (pid, 'Silver/Black', 'Standard', 'Stainless Steel') ON CONFLICT DO NOTHING;

  SELECT id INTO pid FROM stationery_master.products WHERE sku = 'STA-PNCL-000001';
  INSERT INTO stationery_master.stationery_product_details (product_id, color, size, material, grade) VALUES (pid, 'Black/Yellow', 'Standard', 'Wood', 'HB') ON CONFLICT DO NOTHING;

  SELECT id INTO pid FROM stationery_master.products WHERE sku = 'STA-PNCL-000002';
  INSERT INTO stationery_master.stationery_product_details (product_id, color, size, material, grade) VALUES (pid, 'Yellow/Black', 'Standard', 'Cedar Wood', '2B') ON CONFLICT DO NOTHING;
END $$;
