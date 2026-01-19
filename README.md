# AIOSSchedulerTestTool

## 简介

- 用于模拟[AIOS系统](https://github.com/agiresearch/AIOS)中多个Agent向内核并发发送请求的场景
- 可以自行定义请求类型、内容

## 安装

- 将文件放置于形似如下结构的文件夹内
  |- AIOS
    |- ...
    |- SchedulerTool
      |- 项目文件
    |- ...

## 使用

### 配置场景

- 在你需要放置场景配置信息的文件夹下，创建两个文件夹：agents与outputs
- 在agents中，每个yml文件对应一个发送请求的Agent
- Agent文件内的结构参照本项目templates中的内容

### 启动

- 以AIOS为根目录启动agents_simulate_terminal.py
  - python agents_simulate_terminal.py
- 选择场景配置信息所在文件夹（默认为./SchedulerTool/resources
- 输入start启动
- 工具会自动显示当前运行进度

### 查看运行结果

- 工具将结果保存在resources/outputs中，包括响应时间和内容等
- 后期会根据需求添加其他功能
