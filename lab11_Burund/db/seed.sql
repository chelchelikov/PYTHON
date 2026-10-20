-- Тестовые данные
INSERT INTO room_types (id, code, title, description) VALUES
    (1, 'standard', 'Стандарт', 'Номер с одной двуспальной кроватью'),
    (2, 'deluxe',   'Делюкс',   'Улучшенный номер с видом на город'),
    (3, 'suite',    'Люкс',     'Двухкомнатный номер с гостиной'),
    (4, 'family',   'Семейный', 'Номер для семьи с детьми');

INSERT INTO rooms (id, number, type_id, floor, capacity, price, status) VALUES
    (1,  '101', 1, 1, 2, 3500, 'free'),
    (2,  '102', 1, 1, 2, 3200, 'occupied'),
    (3,  '103', 1, 1, 1, 2800, 'free'),
    (4,  '201', 2, 2, 2, 5500, 'free'),
    (5,  '202', 4, 2, 4, 6000, 'free'),
    (6,  '203', 2, 2, 3, 5800, 'maintenance'),
    (7,  '301', 3, 3, 4, 9000, 'booked'),
    (8,  '302', 3, 3, 3, 8500, 'free'),
    (9,  '303', 4, 3, 5, 7000, 'free'),
    (10, '401', 3, 4, 4, 12000, 'free'),
    (11, '402', 1, 4, 2, 3900, 'free'),
    (12, '403', 2, 4, 2, 6200, 'occupied');

INSERT INTO room_photos (room_id, path, is_main) VALUES
    (1, 'images/standard.png', 1),
    (4, 'images/deluxe.png', 1),
    (7, 'images/suite.png', 1),
    (7, 'images/deluxe.png', 0),
    (8, 'images/suite.png', 1),
    (10, 'images/suite.png', 1);

INSERT INTO amenities (id, name) VALUES
    (1, 'Wi-Fi'), (2, 'Кондиционер'), (3, 'Мини-бар'), (4, 'Ванна'),
    (5, 'Вид на море'), (6, 'Детская кровать'), (7, 'Кухня');

INSERT INTO room_amenities (room_id, amenity_id) VALUES
    (1, 1), (2, 1), (3, 1), (4, 1), (4, 2), (5, 1), (5, 6), (5, 7),
    (6, 1), (6, 2), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 3), (8, 4),
    (9, 1), (9, 6), (9, 7), (10, 1), (10, 2), (10, 3), (10, 4), (10, 5),
    (11, 1), (12, 1), (12, 2);

INSERT INTO guests (id, name, email, phone) VALUES
    (1, 'Иванов Иван',     'ivanov@mail.ru',  '+7 900 111-22-33'),
    (2, 'Петрова Анна',    'petrova@mail.ru', '+7 900 222-33-44'),
    (3, 'Сидоров Пётр',    'sidorov@mail.ru', '+7 900 333-44-55'),
    (4, 'Кузнецова Мария', 'kuz@mail.ru',     NULL),
    (5, 'Смирнов Олег',    'smirnov@mail.ru', '+7 900 555-66-77');

INSERT INTO bookings (id, guest_id, check_in, check_out, total_cost, status) VALUES
    (1, 1, '2026-10-18', '2026-10-22', 12800, 'active'),
    (2, 2, '2026-11-01', '2026-11-05', 36000, 'active'),
    (3, 3, '2026-10-19', '2026-10-21', 12400, 'active'),
    (4, 4, '2026-09-01', '2026-09-03', 7000,  'completed'),
    (5, 1, '2026-08-10', '2026-08-12', 17000, 'completed'),
    (6, 5, '2026-12-28', '2027-01-03', 72000, 'cancelled');

INSERT INTO booking_rooms (booking_id, room_id, guests, price) VALUES
    (1, 2, 2, 3200),
    (2, 7, 4, 9000),
    (3, 12, 2, 6200),
    (4, 1, 2, 3500),
    (5, 8, 3, 8500),
    (6, 10, 4, 12000);
