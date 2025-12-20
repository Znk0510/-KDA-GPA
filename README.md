# 你的 KDA 換我的 GPA
## Concept Development 專案簡介
這是一個專為老師設計的教學現場網路控制器，針對上課分心打遊戲、看影片等不務正業的問題。利用 Linux 主機作為教學用 Wi-Fi AP，強迫學生流量經過此閘道器進行監管，同時導入 Telegram 身份綁定、DNS 阻擋以及回答問題等贖罪機制。

可藉由此設計達到：
- 老師登入後台點名 (出缺席)
    - 沒登入 = 離線 -> 缺席
    - 違規次數
- 降低學生上課不專心
- 兩種機制：
    - 知識的贖罪：回答問題理解一點課堂內容 -> 答錯需支付的錢同下 ...
    - 資本的制裁：直接付款 -> 收到的錢拿來獎勵上課專心的同學 ... 等
## Implementation Resources
- Gateway：運行 Ubuntu Linux 的 PC (老師機)，作為軟體路由器連接至 Wi-Fi 基地台。
- 網路介面：
    - WAN：網路來源
    - WLAN：路由器作為 AP 發射訊號
- 終端設備：學生筆電或手機
## Existing Library/Software
| 功能模組 | 技術 | 說明 |
| :--- | :--- | :--- |
| **軟體基地台** | hostapd | 將 Linux 筆電變身為 Wi-Fi AP |
| **Pi-hole** | DNS | 阻擋廣告與色情網站域名、DHCP Server、紀錄 DNS 查詢|
| **登入** | iptables、Nginx、Telegram Bot | 學生連上 Wi-Fi 後需透過 Telegram 登入，telegram bot 詢問資料 |
| **執行懲罰** | iptables、tc | 遊戲：直接 DROP，造成連線逾時<br>影音：限制頻寬 (降速) |
| **出席偵測** | ARP Table Scan | 掃描連線 IP/MAC，比對誰沒有連上網 |
| **勸導頁面** | Nginx | 當學生違規，需至勸導頁面。命運轉盤隨機決定學生：知識的贖罪、資本的制裁 |
| **老師後台** | Vue 3 | 可看全班連線狀態、違規名單與違規次數|
| **AI 出題** | RAG + LLM (Gemma 2:2b) | 老師上傳 PDF 講義，後端自動解析，整合 Ollama (Gemma 2)，生成單選題 |
| **金流** | Telegram Bot | 處理「付費解鎖」請求，學生付款後恢復連線 |

## System Architecture
![image](https://hackmd.io/_uploads/SJ17nNZQ-e.png)

## Implementation Process

## Knowledge from Lecture
iptables、Nginx、DNS
>詳細整理在 Existing Library/Software 

## Installation
```bash
# Clone
git clone <repository_url>
cd smart-classroom

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```
### 資料庫設定
```bash
# 進入 psql
sudo -u postgres psql

# 建立使用者與資料庫 (密碼對應 src/db/database.py 的設定)
CREATE USER lsa WITH PASSWORD 'lsapasswd';
CREATE DATABASE student_guard OWNER lsa;
\q
```
### AI 模型設定 (Ollama)
```bash
# 到瀏覽器開啟 
https://github.com/ollama/ollama/releases

# 找到 v0.13.3，下載
ollama-linux-amd64.tgz

# 解壓縮並安裝
cd ~/Downloads
sudo tar -C /usr -xzf ollama-linux-amd64.tgz

# 建立 Ollama 使用者
sudo useradd -r -s /bin/false -U -m -d /usr/share/ollama ollama
sudo usermod -a -G ollama $(whoami)

# 設定開機服務
sudo vim /etc/systemd/system/ollama.service
# ExecStart 的路徑改成 /usr/bin/ollama

# 啟動服務
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
sudo systemctl status ollama

# 確認 ollama version (0.13.3)
ollama --version

# 下載模型 
ollama pull gemma2:2b
```
### Nginx 設定
將 Nginx config 部署到系統：
1. 複製靜態檔案：將前端檔案移至 Nginx 預設讀取路徑
```BASH
sudo mkdir -p /var/www/portal
# 假設你在專案根目錄
sudo cp -r src/gateway/portal/* /var/www/portal/
```
2. 開放權限讓 Nginx 可以讀取專案靜態檔
```bash
# 讓其他人(包含 Nginx) 可以進入家目錄
# 給 /home/[user] 目錄 execute 權限 (x)，允許進入但不允許列出檔案列表
# [user] 要換成自己
chmod o+x /home/znk

# 確保專案路徑沿途都有權限
chmod o+x /home/[user]/smart-classroom
chmod o+x /home/[user]/smart-classroom/src
chmod o+x /home/[user]/smart-classroom/src/gateway
chmod o+x /home/[user]/smart-classroom/src/gateway/portal

# 確保 index.html 檔案可讀
chmod o+r /home/[user]/smart-classroom/src/gateway/portal/index.html

# 連結設定檔到 Nginx sites-available
sudo ln -s /home/[user]/smart-classroom/config/nginx/smart-classroom.conf /etc/nginx/sites-available/smart-classroom.conf

# 啟用設定檔 (連結到 sites-enabled)
sudo ln -s /etc/nginx/sites-available/smart-classroom.conf /etc/nginx/sites-enabled/

# 連結靜態檔案目錄到 /var/www/portal
# 這樣 Nginx 讀取 /var/www/portal 時，實際上是讀專案中的 src/gateway/portal
sudo ln -s /home/[user]/smart-classroom/src/gateway/portal /var/www/portal

# 檢查
sudo nginx -t
sudo systemctl reload nginx
```
## Usage
1. 啟動後端 API 在 `smart-classroom/` 執行：
```bash
# 啟動 FastAPI
sudo ./venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```
>[!Warning]
>`main.py` 中的 WIFI_INTERFACE 和 TARGET_NETWORK 變數依你的實際網卡名稱修改

---
登入：
學生連到 Linux PC 發射的熱點 -> 點擊 telegram bot 連結 -> 產生結尾是該用戶 IP 的 deep link -> 跟 telegram bot 講學號姓名 -> telegram bot 紀錄 IP、學號、姓名、telegram id、MAC address

---
當學生被鎖網時，須至勸導(懲罰)頁面進行解鎖：
點擊轉盤來決定命運，若抽到：
- 知識的贖罪 (AI 測驗)：後端讀取老師上傳的 PDF，利用 AI 即時生成選擇題
    - 答對 -> 系統解鎖 IP
    - 第一次答錯 -> 會扣 40 顆星 -> 有第二次機會，選擇要 **繼續回答問題解鎖** 還是 **直接接受資本的制裁**
        - 繼續回答，則 AI 繼續生成其他題目，回答錯誤則繼續扣星星(累計計算) -> 回答正確 -> 累計答錯需付出的點數(含第一次答錯) -> 點擊按鈕連結至 Tg Bot 付款 -> 付款完畢 -> 系統解鎖 IP
        - 選 **資本的制裁** -> 加上第一次答錯的扣 40 顆星 + 直接付費解鎖的 100 顆星 -> 點擊按鈕連結至 Tg Bot 付款 -> 付款完畢 -> 系統解鎖 IP
- 資本的制裁 (付費解鎖)
    - 直接付費解鎖的 100 顆星 -> 點擊按鈕連結至 Tg Bot 付款 -> 付款完畢 -> 系統解鎖 IP

## 遇到問題
* 資料庫的合併(SQLite /PostgreSQL)
* 搶port的問題 (已解決)
* 預設 drop https 導致 TG bot 無法進入 (已解決)
* 輪盤頁面不會自動跳轉 (未解)
* 付錢之後的解鎖 (未解)
* 穿透防火牆的幽靈封包 (UDP)

## 未來展望
* 能捕捉「登入/線上」狀態，也可以感知「離線/登出」
* 登入的部分可以讓筆電與手機同時登入
* 可以自動跳轉到輪盤，不用手輸網址

## Job Assignment
> 部分對應 Existing Library/Software 功能模組

|      學號      |       姓名        |                         工作內容                          |
|:--------------:|:-----------------:|:---------------------------------------------------------:|
| 112213011 | 鄒傑丞 | 建立網路環境、系統整合(功能串接、資料庫整合...) |
| 112213015 | 盧鈺博 | Pi-hole、登入、執行懲罰、資料庫 |
| 112213062 | 鄧傑笙 | 處理「付費解鎖」，學生付款後恢復連線 |
| 112213080 | 蔡秉凱 | 主題發想、後端開發、勸導頁面、資料庫、出席偵測、AI 出題、整合老師後台前端 |
| 109213044 | 簡嘉成 | 老師後台前端 |
