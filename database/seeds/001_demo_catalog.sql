-- Idempotent demo seed: 100 rows per catalog. Generic variants intentionally avoid unsupported medical claims.
DO $$ DECLARE k text; ns text; pref text; nm text; cat text; i integer; BEGIN
 FOREACH k IN ARRAY ARRAY['grocery','medical','food','stationery'] LOOP
  ns := k || '_master';
  pref := CASE k WHEN 'grocery' THEN 'GRO' WHEN 'medical' THEN 'MED' WHEN 'food' THEN 'FOOD' ELSE 'STA' END;
  FOR i IN 1..100 LOOP
   cat := CASE k
    WHEN 'grocery' THEN (ARRAY['Staples','Pulses','Spices','Snacks','Beverages','Dairy','Personal Care','Household','Condiments','Cooking Oil'])[((i-1)%10)+1]
    WHEN 'medical' THEN (ARRAY['OTC catalog sample','First aid supplies','Personal care','Medical devices','Wellness','Hygiene','Thermometers','Dressings','Mobility aids','Storage supplies'])[((i-1)%10)+1]
    WHEN 'food' THEN (ARRAY['Raw ingredients','Packaged food','Ready to eat','Frozen food','Bakery','Beverages','Snacks','Dairy','Produce','Food service'])[((i-1)%10)+1]
    ELSE (ARRAY['Writing','Paper','Notebooks','Files','Office supplies','Art supplies','School supplies','Adhesives','Desk accessories','Printer supplies'])[((i-1)%10)+1] END;
   nm := CASE k
    WHEN 'grocery' THEN (ARRAY['Basmati Rice','Wheat Atta','Toor Dal','Turmeric Powder','Red Chilli Powder','Cumin Seeds','Parle-G Biscuits','Masala Snack','Assorted Tea','Packaged Water','Cooking Oil','Tomato Ketchup','Bath Soap','Laundry Detergent','Dishwash Liquid','Poha','Besan','Sugar','Rock Salt','Instant Noodles'])[((i-1)%20)+1]
    WHEN 'medical' THEN (ARRAY['Paracetamol catalog entry','Oral rehydration catalog entry','Adhesive bandage','Sterile gauze dressing','Digital thermometer','Cotton roll','Hand sanitizer','Surgical mask','Hot water bag','Medicine storage box','First aid tape','Disposable gloves','Pill organizer','Wound dressing','Elastic support band','Clinical thermometer','Medical face shield','Nebulizer accessory','Antiseptic catalog entry','Skin care product'])[((i-1)%20)+1]
    WHEN 'food' THEN (ARRAY['Raw Basmati Rice','Whole Wheat Flour','Fresh Paneer','Packaged Yogurt','Frozen Peas','Bakery Bread','Mango Juice','Potato Chips','Fresh Apples','Chicken Food Product','Cooking Cream','Ready Meal','Breakfast Cereal','Bottled Beverage','Cheese Slices','Tomatoes','Lentils','Chocolate Cookies','Frozen Paratha','Packaged Milk'])[((i-1)%20)+1]
    ELSE (ARRAY['Ball Pen','HB Pencil','Eraser','Sharpener','Ruled Notebook','Long Register','Document File','Paper Folder','A4 Paper Ream','Printer Paper','Permanent Marker','Highlighter','Geometry Box','Basic Calculator','Glue Stick','Clear Tape','Safety Scissors','Desk Stapler','Staple Pins','Watercolor Set'])[((i-1)%20)+1] END;
   EXECUTE format('INSERT INTO %I.products(sku,product_name,brand,category,subcategory,description,unit,pack_size,mrp,default_cost_price,default_selling_price,is_active) VALUES ($1,$2,$3,$4,$5,$6,''unit'',$7,100,60,80,true) ON CONFLICT(sku) DO NOTHING',ns)
     USING pref||'-'||upper(substr(regexp_replace(cat,'[^A-Za-z]','','g'),1,4))||'-'||lpad(i::text,6,'0'), nm||' - Catalog Item '||lpad(i::text,3,'0'),
       CASE k WHEN 'grocery' THEN (ARRAY['Tata','Aashirvaad','India Gate','Everest','Parle','Amul','Fortune','Haldiram'])[((i-1)%8)+1] WHEN 'medical' THEN 'Unspecified catalog brand' WHEN 'food' THEN (ARRAY['Amul','Britannia','ITC','Haldiram','Mother Dairy','Tata Consumer'])[((i-1)%6)+1] ELSE (ARRAY['Classmate','Cello','Camlin','Navneet','Kangaro','Faber-Castell'])[((i-1)%6)+1] END,
       cat,'General', 'Demonstration catalog record; verify specifications with supplier.', CASE WHEN i%3=0 THEN 'pack' ELSE 'unit' END;
  END LOOP;
 END LOOP;
END $$;
