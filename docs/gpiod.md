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
