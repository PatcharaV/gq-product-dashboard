# GQ Product & Innovation Explorer

เว็บไซต์สำหรับศึกษา Product Offering ของ GQSize จาก `https://gqsize.com/collections/all`

Public website: `https://gq-product-dashboard.onrender.com`

## ความสามารถหลัก

- ค้นหา กรอง และเรียงสินค้าตามแบรนด์ ประเภท ซีรีส์ ราคา สต็อก และ Innovation
- แยกข้อมูลเป็นหนึ่งแถวต่อหนึ่งรุ่นและสี/ลาย พร้อมรูปและลิงก์ Variant เฉพาะรายการ
- ตัดสินค้าอุปกรณ์ที่ไม่ใช่เสื้อผ้า เช่น หน้ากาก กระเป๋า หมวก และอุปกรณ์ดูแลออก
- แสดง Innovation ของสินค้าแต่ละรายการ พร้อมประโยชน์และข้อความหลักฐานจากข้อมูลต้นทาง
- สรุป Product Mix, Innovation Mix, ช่วงราคา สี และสถานะสินค้า
- ดาวน์โหลดข้อมูลเป็น CSV สำหรับนำไปวิเคราะห์ต่อใน Excel หรือ BI

Innovation ถูกจำแนกอัตโนมัติจากชื่อสินค้า คำอธิบาย และแท็ก จึงควรตรวจสอบกับหน้าสินค้าต้นทางก่อนนำไปใช้เป็นข้อความทางการตลาด

## เปิดเว็บไซต์

```powershell
npm start
```

จากนั้นเปิด `http://localhost:4173`

## อัปเดตข้อมูล

กดปุ่ม `อัปเดตข้อมูล` บนเว็บไซต์ หรือรัน:

```powershell
python scripts\scrape_gqsize.py
```

## ไฟล์ข้อมูล

- `data/gq_products.json` - ข้อมูลเต็มพร้อม variants และ Innovation
- `data/gq_products.csv` - รายการสินค้าแบบตาราง
- `data/gq_products.js` - ข้อมูลสำหรับหน้าเว็บไซต์
- `data/gq_audit.json` - ผลตรวจเทียบ Handle ระหว่างหน้าร้านและ Shopify API พร้อมรายการที่ถูกตัดออก

Endpoints:

- `/api/products` - product dataset JSON
- `/api/refresh` - อัปเดตข้อมูลผ่าน `POST`
- `/health` - ตรวจสอบสถานะ Web Service

## Public Deployment

โปรเจกต์เตรียมไฟล์ `Dockerfile` และ `render.yaml` สำหรับ Render แล้ว:

1. นำโฟลเดอร์นี้ขึ้น GitHub repository
2. เข้า Render และเลือก `New > Blueprint`
3. เชื่อม GitHub repository
4. Render จะอ่าน `render.yaml` และสร้าง Public URL ให้อัตโนมัติ

หมายเหตุ: Free Web Service ใช้ filesystem ชั่วคราว ข้อมูลที่อัปเดตผ่านปุ่มบนเว็บอาจกลับเป็นไฟล์จาก GitHub เมื่อ Service restart ควร commit dataset ใหม่หรือ redeploy เมื่อต้องการเก็บข้อมูลถาวร
