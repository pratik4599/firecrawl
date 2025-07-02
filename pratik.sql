cd /home/aqdev/pratik/firescale/firecrawl/firecrawl-load-balancer

-- run flask app as root (req for docker restart)
nohup python3 app.py > /dev/null 2>&1 &



