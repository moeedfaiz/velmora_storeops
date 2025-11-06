INSERT INTO suppliers(name, email) VALUES
 ('Velmora Core','ops@velmora.pk'),
 ('Premium Textiles','hello@premium-tex.com');

INSERT INTO products(sku, name, price, supplier_id) VALUES
 ('VLM-TEE-001','Velmora Tee Black S', 1499, 1),
 ('VLM-TEE-002','Velmora Tee Black M', 1499, 1),
 ('VLM-TEE-003','Velmora Tee Black L', 1499, 1),
 ('VLM-JNS-001','Velmora Jeans 32',   4499, 2);

INSERT INTO inventory(sku, on_hand, reorder_point, reorder_qty) VALUES
 ('VLM-TEE-001', 22, 10, 60),
 ('VLM-TEE-002', 12, 10, 60),
 ('VLM-TEE-003',  4, 10, 60),
 ('VLM-JNS-001', 18,  6, 30);

-- A couple of orders with items
INSERT INTO orders(customer_name, status) VALUES
 ('Ali Hamza','Shipped'),
 ('Ayesha Noor','Packed'),
 ('Hassan Raza','Paid');

INSERT INTO order_items(order_id, sku, qty, price) VALUES
 (1,'VLM-TEE-001', 2, 1499),
 (1,'VLM-JNS-001', 1, 4499),
 (2,'VLM-TEE-003', 1, 1499),
 (3,'VLM-TEE-002', 3, 1499);
