# 從官方 Python 3.11.1 鏡像作為基礎鏡像
FROM python:3.11.1

# 將當前目錄的內容複製到容器的 /app 目錄
COPY . /app

# 將工作目錄設定為容器的 /app 目錄
WORKDIR /app

# 更新套件庫並安裝 unixodbc 和 unixodbc-dev，這兩個套件用於連接 SQL Server
RUN apt-get update && apt-get install -y unixodbc unixodbc-dev curl gnupg

# 從 Microsoft 的套件庫下載公鑰並添加到 apt
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -

# 添加 Microsoft 的 SQL Server Ubuntu 套件庫
RUN curl https://packages.microsoft.com/config/ubuntu/19.10/prod.list > /etc/apt/sources.list.d/mssql-release.list

# 更新套件庫並安裝 MS SQL ODBC 驅動程式
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# 安裝 requirements.txt 中指定的所有需要的 Python 套件
RUN pip install --no-cache-dir -r requirements.txt

# 當容器啟動時，運行 main.py
CMD ["python", "main.py"]