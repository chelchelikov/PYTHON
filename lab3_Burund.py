"""Лабораторная работа №3. Вариант 5. Автопарк."""

from abc import ABC, abstractmethod


class Engine:
    """Двигатель транспортного средства (используется через композицию)."""

    def __init__(self, power_hp, fuel_consumption):
        self.power_hp = power_hp
        self.fuel_consumption = fuel_consumption  # литров на 100 км

    def fuel_for(self, distance_km):
        return distance_km * self.fuel_consumption / 100

    def __str__(self):
        return f"{self.power_hp} л.с., {self.fuel_consumption} л/100 км"


class Vehicle(ABC):
    """Базовый класс транспортного средства."""

    vehicle_count = 0

    def __init__(self, reg_number, model, engine, mileage=0):
        self.reg_number = reg_number
        self.model = model
        self.engine = engine
        self._mileage = 0
        self.mileage = mileage
        self.trips = []
        self.in_service = False
        Vehicle.vehicle_count += 1

    @property
    def mileage(self):
        return self._mileage

    @mileage.setter
    def mileage(self, value):
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError("Пробег должен быть неотрицательным числом")
        if value < self._mileage:
            raise ValueError("Пробег нельзя уменьшить")
        self._mileage = value

    def drive(self, distance_km):
        if self.in_service:
            raise RuntimeError(f"{self.reg_number} находится на обслуживании")
        if distance_km <= 0:
            raise ValueError("Расстояние должно быть положительным")
        self.mileage = self._mileage + distance_km
        self.trips.append(distance_km)
        return self.engine.fuel_for(distance_km)

    def send_to_service(self):
        self.in_service = True

    def return_from_service(self):
        self.in_service = False

    def total_distance(self):
        return sum(self.trips)

    @abstractmethod
    def transport_indicator(self):
        """Транспортный показатель: объём перевозок за все поездки."""

    @abstractmethod
    def indicator_unit(self):
        pass

    def type_name(self):
        return "Транспортное средство"

    def __str__(self):
        status = "на обслуживании" if self.in_service else "в работе"
        return (f"{self.type_name()} {self.model} [{self.reg_number}], "
                f"пробег {self._mileage} км, двигатель: {self.engine}, {status}")


class Car(Vehicle):
    def __init__(self, reg_number, model, engine, passengers, mileage=0):
        super().__init__(reg_number, model, engine, mileage)
        if passengers <= 0:
            raise ValueError("Количество пассажиров должно быть положительным")
        self.passengers = passengers

    def transport_indicator(self):
        return self.passengers * self.total_distance()

    def indicator_unit(self):
        return "пасс.-км"

    def type_name(self):
        return "Легковой автомобиль"

    def __str__(self):
        return f"{super().__str__()}, пассажиров: {self.passengers}"


class Truck(Vehicle):
    def __init__(self, reg_number, model, engine, capacity_t, mileage=0):
        super().__init__(reg_number, model, engine, mileage)
        if capacity_t <= 0:
            raise ValueError("Грузоподъёмность должна быть положительной")
        self.capacity_t = capacity_t

    def transport_indicator(self):
        return self.capacity_t * self.total_distance()

    def indicator_unit(self):
        return "т-км"

    def type_name(self):
        return "Грузовик"

    def drive(self, distance_km):
        # Гружёный грузовик расходует больше топлива: +2% на каждую тонну
        fuel = super().drive(distance_km)
        return fuel * (1 + 0.02 * self.capacity_t)

    def __str__(self):
        return f"{super().__str__()}, грузоподъёмность: {self.capacity_t} т"


class Fleet:
    """Автопарк, содержащий транспортные средства."""

    def __init__(self, name):
        self.name = name
        self._vehicles = []
        self.fuel_used = 0.0

    def add(self, vehicle):
        if self.find(vehicle.reg_number):
            raise ValueError(f"ТС с номером {vehicle.reg_number} уже есть в автопарке")
        self._vehicles.append(vehicle)

    def remove(self, reg_number):
        vehicle = self.find(reg_number)
        if vehicle is None:
            raise KeyError(f"ТС с номером {reg_number} не найдено")
        self._vehicles.remove(vehicle)

    def find(self, reg_number):
        for vehicle in self._vehicles:
            if vehicle.reg_number == reg_number:
                return vehicle
        return None

    def dispatch(self, reg_number, distance_km):
        vehicle = self.find(reg_number)
        if vehicle is None:
            raise KeyError(f"ТС с номером {reg_number} не найдено")
        fuel = vehicle.drive(distance_km)
        self.fuel_used += fuel
        return fuel

    def available(self):
        return [v for v in self._vehicles if not v.in_service]

    def report(self):
        print(f"\n===== Автопарк «{self.name}» =====")
        for vehicle in self._vehicles:
            print(vehicle)

    def indicators(self):
        print("\nТранспортные показатели:")
        for vehicle in self._vehicles:
            print(f"  {vehicle.reg_number}: {vehicle.transport_indicator():.1f} "
                  f"{vehicle.indicator_unit()}")

    def statistics(self):
        cars = [v for v in self._vehicles if isinstance(v, Car)]
        trucks = [v for v in self._vehicles if isinstance(v, Truck)]
        print("\nСтатистика автопарка:")
        print(f"  Всего ТС: {len(self._vehicles)} (легковых: {len(cars)}, грузовиков: {len(trucks)})")
        print(f"  Доступно для рейсов: {len(self.available())}")
        print(f"  Общий пробег: {sum(v.mileage for v in self._vehicles)} км")
        print(f"  Пассажировместимость: {sum(c.passengers for c in cars)} чел.")
        print(f"  Суммарная грузоподъёмность: {sum(t.capacity_t for t in trucks)} т")
        print(f"  Израсходовано топлива: {self.fuel_used:.1f} л")

    def __len__(self):
        return len(self._vehicles)


def main():
    fleet = Fleet("Северный")

    print("Тест 1. Создание объектов каждого типа")
    fleet.add(Car("А123ВС", "Lada Vesta", Engine(106, 7.5), passengers=4, mileage=15000))
    fleet.add(Car("В456ОР", "Kia Rio", Engine(123, 6.9), passengers=4))
    fleet.add(Truck("Е789КХ", "КАМАЗ-5490", Engine(428, 32.0), capacity_t=18, mileage=50000))
    fleet.add(Truck("М321ТТ", "ГАЗель Next", Engine(149, 12.0), capacity_t=1.5))
    print(f"Создано транспортных средств: {Vehicle.vehicle_count}, в автопарке: {len(fleet)}")
    fleet.report()

    print("\nТест 2–3. Общие и переопределённые методы (рейсы)")
    for reg_number, distance in [("А123ВС", 120), ("В456ОР", 80),
                                 ("Е789КХ", 400), ("М321ТТ", 150), ("А123ВС", 60)]:
        fuel = fleet.dispatch(reg_number, distance)
        print(f"  {reg_number}: рейс {distance} км, топливо {fuel:.1f} л")

    print("\nТест 4. Изменение состояния объекта")
    truck = fleet.find("М321ТТ")
    truck.send_to_service()
    print(" ", truck)
    try:
        fleet.dispatch("М321ТТ", 10)
    except RuntimeError as error:
        print("  Ошибка:", error)
    truck.return_from_service()

    print("\nТест 5. Некорректное значение свойства")
    car = fleet.find("А123ВС")
    for value in (-5, 100):
        try:
            car.mileage = value
        except ValueError as error:
            print(f"  mileage = {value}: {error}")

    print("\nТест 6. Полиморфная коллекция")
    fleet.indicators()

    print("\nТест 7. Композиция: Fleet -> Vehicle -> Engine")
    for vehicle in fleet.available():
        print(f"  {vehicle.reg_number}: двигатель {vehicle.engine}")

    fleet.remove("В456ОР")
    fleet.report()
    fleet.statistics()


if __name__ == "__main__":
    main()
