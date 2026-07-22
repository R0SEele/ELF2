# import gpiod
导入 gpiod 库

# chip = gpiod.Chip('gpiodchipN')
初始化gpio芯片

# line = chip.get_line(n)
获取GPIO引脚的引用

# line.request(consumer='my_gpio',type=gpiod.LINE_REQ_DIR_OUT)
将GPIO引脚设置为输出模式
LINE_REQ_DIR_OUT 输出
LINE_REQ_DIR_IN  输入
my_gpio是名称，不影响使用

# line.release()
释放引脚，与line.request相对，有始有终

# value = line.get_value()
读取GPIO引脚的状态

# line.set_value(1)
写入GPIO引脚的状态

## 本项目风扇 GPIO3_B3

`GPIO3_B3` 按 RK3588 命名规则是 GPIO bank 3 的 B 组第 3 位：全局编号为 `3 * 32 + 1 * 8 + 3 = 107`。字符设备通常对应 `/dev/gpiochip3` 的 line 11，项目配置见 `config/fan.yaml`。

首次上板后先确认实际芯片和 line 名称：

```bash
gpioinfo /dev/gpiochip3 | grep -i GPIO3_B3
```

如果系统的 gpiochip 编号不同，只修改 `config/fan.yaml` 的 `chip`；如果 line offset 不同，按 `gpioinfo` 的实际结果修改 `line_offset`。执行 `sudo src/hardware/sensors/setup_sensor_permissions.sh <用户名>` 给 Qt、传感器采集和风扇脚本配置 `/dev/gpiochip*` 权限。

风扇驱动默认高电平开启、低电平关闭。先断开风扇功率级，仅连接示波器或万用表验证，再执行：

```bash
python3 src/hardware/fan/ventilation_fan.py on
python3 src/hardware/fan/ventilation_fan.py off
```
