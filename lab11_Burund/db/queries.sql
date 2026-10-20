-- Лабораторная работа №11. Вариант 5. Отель — SQL-запросы.
-- Каждый запрос отделён строкой «-- N. описание»; run_queries.py выполняет их по очереди.

-- 1. SELECT: все номера
SELECT * FROM rooms;

-- 2. WHERE: свободные номера
SELECT number, floor, capacity, price FROM rooms WHERE status = 'free';

-- 3. ORDER BY: номера от дорогих к дешёвым
SELECT number, price FROM rooms ORDER BY price DESC, number;

-- 4. JOIN: номера с названием типа
SELECT r.number, t.title, r.price
FROM rooms r
JOIN room_types t ON t.id = r.type_id
ORDER BY r.number;

-- 5. LEFT JOIN: номера и их главные фото (у части номеров фото нет)
SELECT r.number, p.path
FROM rooms r
LEFT JOIN room_photos p ON p.room_id = r.id AND p.is_main = 1
ORDER BY r.number;

-- 6. GROUP BY + COUNT: количество номеров каждого типа
SELECT t.title, COUNT(r.id) AS rooms_count
FROM room_types t
LEFT JOIN rooms r ON r.type_id = t.id
GROUP BY t.id
ORDER BY rooms_count DESC;

-- 7. HAVING: типы номеров, где больше двух номеров
SELECT t.title, COUNT(*) AS rooms_count
FROM rooms r
JOIN room_types t ON t.id = r.type_id
GROUP BY t.id
HAVING COUNT(*) > 2;

-- 8. COUNT: число номеров по статусам
SELECT status, COUNT(*) AS cnt FROM rooms GROUP BY status;

-- 9. AVG: средняя, минимальная и максимальная цена по этажам
SELECT floor, ROUND(AVG(price), 2) AS avg_price, MIN(price) AS min_price, MAX(price) AS max_price
FROM rooms GROUP BY floor;

-- 10. SUM: выручка (без отменённых бронирований)
SELECT SUM(total_cost) AS revenue FROM bookings WHERE status <> 'cancelled';

-- 11. INSERT: новый гость
INSERT INTO guests (name, email, phone) VALUES ('Новиков Денис', 'novikov@mail.ru', '+7 900 999-00-11');

-- 12. UPDATE: повышение цен на люксы на 5 %
UPDATE rooms SET price = ROUND(price * 1.05, 2)
WHERE type_id = (SELECT id FROM room_types WHERE code = 'suite');

-- 13. DELETE: удаление гостя без бронирований
DELETE FROM guests WHERE email = 'novikov@mail.ru'
  AND id NOT IN (SELECT guest_id FROM bookings);

-- 14. Подзапрос: номера дороже средней цены
SELECT number, price FROM rooms
WHERE price > (SELECT AVG(price) FROM rooms)
ORDER BY price;

-- 15. Несколько условий: свободные номера на 3+ гостей дешевле 8000 и без ремонта
SELECT number, capacity, price FROM rooms
WHERE status = 'free' AND capacity >= 3 AND price < 8000
ORDER BY price;

-- 16. Связь нескольких таблиц: история бронирований гостей с номерами и типами
SELECT g.name, b.check_in, b.check_out, r.number, t.title, b.status, b.total_cost
FROM bookings b
JOIN guests g         ON g.id = b.guest_id
JOIN booking_rooms br ON br.booking_id = b.id
JOIN rooms r          ON r.id = br.room_id
JOIN room_types t     ON t.id = r.type_id
ORDER BY b.check_in;

-- 17. N:M: удобства каждого номера одной строкой
SELECT r.number, GROUP_CONCAT(a.name, ', ') AS amenities
FROM rooms r
JOIN room_amenities ra ON ra.room_id = r.id
JOIN amenities a       ON a.id = ra.amenity_id
GROUP BY r.id
ORDER BY r.number;

-- 18. Специализированный запрос: номера, свободные на период 2026-11-02 — 2026-11-04 для 2 гостей
SELECT r.number, r.capacity, r.price
FROM rooms r
WHERE r.status <> 'maintenance'
  AND r.capacity >= 2
  AND NOT EXISTS (
      SELECT 1 FROM booking_rooms br
      JOIN bookings b ON b.id = br.booking_id
      WHERE br.room_id = r.id
        AND b.status = 'active'
        AND b.check_in < '2026-11-04'
        AND b.check_out > '2026-11-02')
ORDER BY r.price;

-- 19. Гости, потратившие больше 15000 (GROUP BY + HAVING + SUM)
SELECT g.name, SUM(b.total_cost) AS spent, COUNT(b.id) AS visits
FROM guests g
JOIN bookings b ON b.guest_id = g.id
WHERE b.status <> 'cancelled'
GROUP BY g.id
HAVING SUM(b.total_cost) > 15000
ORDER BY spent DESC;

-- 20. EXPLAIN: использование индекса при поиске свободных номеров
EXPLAIN QUERY PLAN
SELECT number FROM rooms WHERE status = 'free' AND capacity >= 3;
