#!/bin/bash
init_firewall.sh - 完整初始化 Captive Portal 防火牆
echo "🧹 1. 清空舊規則..."
sudo iptables -F
sudo iptables -t nat -F

echo "🌐 2. 放行 DNS (不然誰都連不上)..."
sudo iptables -I FORWARD -s 192.168.100.0/24 -p udp --dport 53 -j ACCEPT
sudo iptables -I FORWARD -s 192.168.100.0/24 -p tcp --dport 53 -j ACCEPT

echo "✈️ 3. 放行 Telegram (Walled Garden)..."
./allow_telegram.sh

echo "🕸️ 4. 架設 HTTP 陷阱 (Port 80 -> Login Page)..."
sudo iptables -t nat -A PREROUTING -p tcp -s 192.168.100.0/24 --dport 80 -j DNAT --to-destination 192.168.100.1:81

echo "🛡️ 5. 封鎖其餘流量 (HTTPS/遊戲)..."
注意：因為上面用 -I (Insert) 插在最前面，這條 DROP 用 -A (Append) 放在最後面剛好
sudo iptables -A FORWARD -s 192.168.100.0/24 -j DROP

echo "✅ 防火牆設定完成！"
