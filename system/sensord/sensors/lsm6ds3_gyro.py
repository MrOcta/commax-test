import time
import math

from cereal import log
from openpilot.system.sensord.sensors.i2c_sensor import I2CSensor

class LSM6DS3_Gyro(I2CSensor):
  # Register addresses
  LSM6DS3_GYRO_I2C_REG_DRDY_CFG = 0x0B
  LSM6DS3_GYRO_I2C_REG_ID = 0x0F
  LSM6DS3_GYRO_I2C_REG_INT1_CTRL = 0x0D
  LSM6DS3_GYRO_I2C_REG_CTRL2_G = 0x11
  LSM6DS3_GYRO_I2C_REG_CTRL5_C = 0x14
  LSM6DS3_GYRO_I2C_REG_STAT_REG = 0x1E
  LSM6DS3_GYRO_I2C_REG_OUTX_L_G = 0x22

  # Constants
  LSM6DS3_GYRO_CHIP_ID = 0x69
  LSM6DS3TRC_GYRO_CHIP_ID = 0x6A
  LSM6DS3_GYRO_ODR_104HZ = (0b0100 << 4)
  LSM6DS3_GYRO_ODR_208HZ = (0b0101 << 4)
  LSM6DS3_GYRO_FS_2000dps = (0b11 << 2)
  LSM6DS3_GYRO_INT1_DRDY_G = 0b10
  LSM6DS3_GYRO_DRDY_GDA = 0b10
  LSM6DS3_GYRO_DRDY_PULSE_MODE = (1 << 7)
  LSM6DS3_GYRO_POSITIVE_TEST = (0b01 << 2)
  LSM6DS3_GYRO_NEGATIVE_TEST = (0b11 << 2)
  LSM6DS3_GYRO_MIN_ST_LIMIT_mdps = 150000.0
  LSM6DS3_GYRO_MAX_ST_LIMIT_mdps = 700000.0

  @property
  def device_address(self) -> int:
    return 0x6A

  def init(self):
    chip_id = self.verify_chip_id(self.LSM6DS3_GYRO_I2C_REG_ID, [0x69, 0x6A])
    if chip_id == 0x6A:
      self.source = log.SensorEventData.SensorSource.lsm6ds3trc
    else:
      self.source = log.SensorEventData.SensorSource.lsm6ds3

    self.init_gpio()

    self.writes((
      # TODO: set scale. Default is +- 250 deg/s
      (self.LSM6DS3_GYRO_I2C_REG_CTRL2_G, self.LSM6DS3_GYRO_ODR_104HZ),
      # Configure data ready signal to pulse mode
      (self.LSM6DS3_GYRO_I2C_REG_DRDY_CFG, self.LSM6DS3_GYRO_DRDY_PULSE_MODE),
    ))

    # Enable data ready interrupt on INT1 without resetting existing interrupts
    value = self.read(self.LSM6DS3_GYRO_I2C_REG_INT1_CTRL, 1)[0]
    value |= self.LSM6DS3_GYRO_INT1_DRDY_G
    self.write(self.LSM6DS3_GYRO_I2C_REG_INT1_CTRL, value)

  def get_event(self, ts: int | None = None) -> log.SensorEventData:
    # Check if gyroscope data is ready
    status_reg = self.read(self.LSM6DS3_GYRO_I2C_REG_STAT_REG, 1)[0]
    if not (status_reg & self.LSM6DS3_GYRO_DRDY_GDA):
      raise Exception

    # Read 6 bytes (X, Y, Z low and high)
    b = self.read(self.LSM6DS3_GYRO_I2C_REG_OUTX_L_G, 6)
    x = math.radians(self.parse_16bit(b[0], b[1]))
    y = math.radians(self.parse_16bit(b[2], b[3]))
    z = math.radians(self.parse_16bit(b[4], b[5]))

    # Scale to rad/s for ±250 dps range
    scale = (8.75 / 1000.0) * (math.pi / 180.0)
    xyz = [y * scale, -x * scale, z * scale]

    event = log.SensorEventData.new_message()
    event.timestamp = ts if ts is not None else int(time.monotonic() * 1e9)
    event.version = 2
    event.sensor = 5  # SENSOR_GYRO_UNCALIBRATED
    event.type = 16   # SENSOR_TYPE_GYROSCOPE_UNCALIBRATED
    event.source = self.source

    g = event.init('gyroUncalibrated')
    g.v = xyz
    g.status = 1

    return event

  def shutdown(self) -> None:
    # Disable data ready interrupt on INT1
    value = self.read(self.LSM6DS3_GYRO_I2C_REG_INT1_CTRL, 1)[0]
    value &= ~self.LSM6DS3_GYRO_INT1_DRDY_G
    self.write(self.LSM6DS3_GYRO_I2C_REG_INT1_CTRL, value)

    # Power down by clearing ODR bits
    value = self.read(self.LSM6DS3_GYRO_I2C_REG_CTRL2_G, 1)[0]
    value &= 0x0F
    self.write(self.LSM6DS3_GYRO_I2C_REG_CTRL2_G, value)

if __name__ == "__main__":
  s = LSM6DS3_Gyro(1)
  s.init()
  print(s.get_event())
  s.shutdown()
