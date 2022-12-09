import dataclasses
import random
import statistics
from typing import ClassVar, Callable

from simpy import Resource, Environment

import settings

random.seed(2 ** 25)


@dataclasses.dataclass
class MonitoringData:
    time: int
    queue_length: int
    active_users: int


class MonitoredResource(Resource):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data: list[MonitoringData] = []

    def request(self, *args, **kwargs):
        self.data.append(
            MonitoringData(
                time=self._env.now,
                queue_length=len(self.queue) + self.count,
                active_users=self.count
            )
        )
        return super().request()

    def release(self, *args, **kwargs):
        self.data.append(
            MonitoringData(
                time=self._env.now,
                queue_length=len(self.queue),
                active_users=self.count
            )
        )

        return super().release(*args, **kwargs)


class GasStation:
    GAS_TANK_EMPTY_CHANCE: ClassVar[float] = 0.05
    CUSTOMER_WANTS_FOOD_CHANCE: ClassVar[float] = 0.25
    CUSTOMER_RETARDED_CHANCE: ClassVar[float] = 0.35

    def __init__(self, environment: Environment) -> None:
        self._environment: Environment = environment
        self._gas_tank = MonitoredResource(environment, settings.GAS_TANKS_NUMBER)
        self._cashier = MonitoredResource(environment, settings.CASHIERS_NUMBER)
        self._waiting_time_values: list[int] = []

    def _sell_food(self):
        yield self._environment.timeout(
            random.randint(
                settings.AVERAGE_CASHIER_SERVICE_TIME - settings.DEVIATION,
                settings.AVERAGE_CASHIER_SERVICE_TIME + settings.DEVIATION
            )
        )

    def _fill_up_car(self):
        yield self._environment.timeout(
            random.randint(
                settings.AVERAGE_SERVICE_TIME - settings.DEVIATION,
                settings.AVERAGE_SERVICE_TIME + settings.DEVIATION
            )
        )

    def _fill_up_car_slowly(self):
        yield self._environment.timeout(
            random.randint(
                settings.AVERAGE_SERVICE_TIME - settings.DEVIATION,
                settings.AVERAGE_SERVICE_TIME + settings.DEVIATION
            ) * 2
        )

    def _fill_up_tank(self):
        yield self._environment.timeout(
            random.randint(
                settings.AVERAGE_FILL_UP_TANK_SERVICE_TIME - settings.DEVIATION,
                settings.AVERAGE_FILL_UP_TANK_SERVICE_TIME + settings.DEVIATION
            )
        )

    def process(self):
        arrival_time: int = self._environment.now
        dice: float = random.random()

        if dice <= self.GAS_TANK_EMPTY_CHANCE:
            with self._gas_tank.request() as request:
                yield request
                yield self._environment.process(self._fill_up_tank())
            print(self._environment.now, f"Бензоколонка пустая, посетитель ждет, пока ее наполнят")

        if dice <= self.CUSTOMER_RETARDED_CHANCE:
            with self._gas_tank.request() as request:
                yield request
                yield self._environment.process(self._fill_up_car_slowly())
            print(self._environment.now, "Посетитель не смог разобраться с процессом заправки и задержался")
        else:
            with self._gas_tank.request() as request:
                yield request
                yield self._environment.process(self._fill_up_car())

        dice = random.random()
        if dice < self.CUSTOMER_WANTS_FOOD_CHANCE:
            with self._cashier.request() as request:
                yield request
                yield self._environment.process(self._sell_food())
            print(self._environment.now, f"Посетитель захотел поесть и зашел в мини-магазин")

        self._waiting_time_values.append(self._environment.now - arrival_time)

    def get_statistics(self) -> tuple[list[MonitoringData], list[MonitoringData]]:
        return self._gas_tank.data, self._cashier.data

    def get_mean_waiting_time(self):
        return statistics.mean(self._waiting_time_values)


class MyEnvironment:
    def __init__(self) -> None:
        self._environment: Environment = Environment()
        self._system = GasStation(self._environment)
        self.get_mean_waiting_time: Callable = self._system.get_mean_waiting_time
        self.get_statistics: Callable = self._system.get_statistics

    def _run_system(self):
        while True:
            time_between_tasks: int = random.randint(
                settings.AVERAGE_TIME_BETWEEN_TASKS - settings.DEVIATION,
                settings.AVERAGE_TIME_BETWEEN_TASKS + settings.DEVIATION,
            )
            yield self._environment.timeout(time_between_tasks)

            self._environment.process(self._system.process())


    def run(self, until: int):
        self._environment.process(self._run_system())
        self._environment.run(until)


def main() -> None:
    environment = MyEnvironment()
    WORKING_DAY: int = 24 * 60 * 60

    print("Моделирование автозаправки запущено")
    environment.run(until=WORKING_DAY)
    print(f"\nСреднее время ожидания {round(environment.get_mean_waiting_time(), 4)} секунд.")
    gas_monitoring_data, cashier_monitoring_data = environment.get_statistics()

    demand: int = 0
    usage: int = 0
    last_monitor_time: int = 0

    for monitor in gas_monitoring_data:
        demand += monitor.queue_length * (monitor.time - last_monitor_time)
        usage += monitor.active_users * (monitor.time - last_monitor_time)
        last_monitor_time = monitor.time

    demand /= WORKING_DAY
    usage /= WORKING_DAY
    print(
        f"\nКоэффициент использования бензоколонки {round(usage / settings.GAS_TANKS_NUMBER * 100, 2)}%.",
        f"\nCреднее по времени число требований в очереди на бензоколонку: {round(demand, 4)}.",
    )

    demand = 0
    usage = 0
    last_monitor_time = 0

    for monitor in cashier_monitoring_data:
        demand += monitor.queue_length * (monitor.time - last_monitor_time)
        usage += monitor.active_users * (monitor.time - last_monitor_time)
        last_monitor_time = monitor.time

    demand /= WORKING_DAY
    usage /= WORKING_DAY
    print(
        f"\nКоэффициент использования кассы {round(usage / settings.CASHIERS_NUMBER * 100, 2)}%.",
        f"\nCреднее по времени число требований в очереди на кассу: {round(demand, 4)}.",
    )


if __name__ == '__main__':
    main()
