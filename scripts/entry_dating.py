import os, sys, json, datetime, socket, random, publicsuffixlist, ssl
import dns.resolver

dead_domains = []
p = publicsuffixlist.PublicSuffixList(only_icann=True)
resolver = dns.resolver.Resolver()
resolver.nameservers = ["https://unfiltered.adguard-dns.com/dns-query","94.140.14.140", "8.8.8.8","1.1.1.1"]
already_resolved = {}
known_whois = {}

def get_whois_data_raw(domain, server):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((server, 43))
    all_data = b""
    s.send("{domain}\r\n".replace("{domain}", domain).encode())
    while True:
        try:
            newdata = s.recv(100)
            if len(newdata) == 0:
                break
            all_data += newdata
        except Exception:
            break
    s.close()
    return all_data.decode()

def get_whois(domain):
    global known_whois
    if domain in known_whois:
        return known_whois[domain]
    tld = p.publicsuffix(domain).upper()
    server = f"{tld}.whois-servers.net"
    try:
        whois_data = get_whois_data_raw(domain, server)
    except:
        return ""
    known_whois[domain] = whois_data
    return whois_data

def whois_exists(domain):
    global dead_domains
    if domain.endswith(".onion"): # onion domains do not have WHOIS records
        return True
    try:
        whois_data = get_whois(domain)
        if "No match for" in whois_data or "No Data Found" in whois_data or "No whois information found" in whois_data or "%% NOT FOUND" in whois_data or f'Error for "{domain}"' in whois_data or "This domain cannot be registered because" in whois_data or "The queried object does not exist:" in whois_data or "DOMAIN NOT FOUND" in whois_data:
            return False
        return whois_data != ""
    except:
        return False

def is_alive(domain, in_list=True):
    global dead_domains
    global already_resolved
    if domain in already_resolved:
        return True
    if domain in dead_domains:
        return False
    if domain.endswith(".onion"): # can't test onions yet
        return True
    try:
        res_ips = list(resolver.resolve(domain))
        found_ips = []
        for ip in res_ips:
            found_ips.append(ip.address)
        already_resolved[domain] = found_ips
        return True
    except:
        if domain not in dead_domains and whois_exists(domain) == False and in_list:
            dead_domains.append(domain)
        return False

def get_ips(domain):
    global already_resolved
    if domain in already_resolved:
        return already_resolved[domain]
    if domain in dead_domains:
        return []
    try:
        res_ips = list(resolver.resolve(domain))
        found_ips = []
        for ip in res_ips:
            found_ips.append(ip.address)
        already_resolved[domain] = found_ips
        return found_ips
    except:
        return []

def is_valid(domain):
    try:
        return p.publicsuffix(domain, accept_unknown=False) != None
    except:
        return False

def port_open(host, port):
    try:
        s = socket.socket()
        return s.connect_ex((host, port)) == 0
    except:
        return False

def get_tls_info(hostname):
    # https://stackoverflow.com/questions/41620369/how-to-get-ssl-certificate-details-using-python
    context = ssl.create_default_context()
    context.check_hostname = False
    conn = context.wrap_socket(
        socket.socket(socket.AF_INET),
        server_hostname=hostname,
    )
    # 5 second timeout
    conn.settimeout(5.0)

    conn.connect((hostname, 443))
    ssl_info = conn.getpeercert()
    return ssl_info

try:
    entry_data = json.loads(open("entry_data.json", encoding="UTF-8").read())
except:
    entry_data = {}

domain_list = open("Alternative list formats/antimalware_domains.txt", encoding="UTF-8").read().replace("\r\n","\n").split("\n")
current_date = datetime.datetime.now().isoformat()
entry_data["last_updated"] = current_date

# recheck a random entry regardless of it's status
random_recheck = None
try:
    random_recheck = random.choice(domain_list)
    print('random recheck',entry_data[random_recheck]['check_counter'], entry_data[random_recheck]['first_seen'] , random_recheck)
    if random_recheck in entry_data:
        entry_data[random_recheck]['check_counter'] = 55
except Exception as err:
    print('random recheck failed', err)

for e in domain_list:
    #print(e, e in entry_data)
    if (e not in entry_data or type(entry_data[e]) == str) and e != "last_updated":
        entry_is_alive = is_alive(e, True)
        dead_since = ""
        if entry_is_alive != True:
            dead_since = current_date
        tls_info = {}
        if port_open(e, 443):
            try:
                tls_info = get_tls_info(e)
            except:
                pass
        entry_data[e] = {
            "first_seen": current_date,
            "last_seen": current_date,
            "removed": False,
            "removed_date": "",
            "last_checked": current_date,
            "check_counter": random.randint(20, 30),
            "check_status": entry_is_alive,
            "alive_on_creation": entry_is_alive,
            "times_checked": 1,
            "ever_rechecked": False,
            "readded": False,
            "alive_on_removal": None,
            "origin_add": "",
            "readd": "",
            "is_valid": is_valid(e),
            "ips": get_ips(e),
            "dead_since": dead_since,
            "whois": get_whois(e),
            "ports_open": {
                23: port_open(e, 23), # https://threatfox.abuse.ch/ioc/1252534/
                80: port_open(e, 80),
                81: port_open(e, 81), # https://threatfox.abuse.ch/ioc/1252558/
                100: port_open(e, 100), # https://threatfox.abuse.ch/ioc/1252471/
                443: port_open(e, 443),
                666: port_open(e, 666), # has been used (https://www.grc.com/port_666.htm, https://www.aircrack-ng.org/doku.php?id=airserv-ng)
                671: port_open(e, 671), # https://threatfox.abuse.ch/ioc/1252557/
                1337: port_open(e, 1337), # leet h@ck0rz
                2222: port_open(e, 2222), # https://threatfox.abuse.ch/ioc/1252501/
                3333: port_open(e, 3333), # https://threatfox.abuse.ch/ioc/1252536/
                4880: port_open(e, 4880), # https://threatfox.abuse.ch/ioc/1252530/
                5000: port_open(e, 5000), # default port for python flask
                6666: port_open(e, 6666), # https://threatfox.abuse.ch/ioc/1252550/
                7443: port_open(e, 7443), # https://threatfox.abuse.ch/ioc/1252812/
                8000: port_open(e, 8000),
                8080: port_open(e, 8080),
                8081: port_open(e, 8081), # https://threatfox.abuse.ch/ioc/1252815/
                8443: port_open(e, 8443), # https://threatfox.abuse.ch/ioc/1252551/
                8888: port_open(e, 8888), # https://threatfox.abuse.ch/ioc/1252820/
                9090: port_open(e, 9090), # default port for updog
                50000: port_open(e, 50000), # https://threatfox.abuse.ch/ioc/1252509/
            },
            "had_www_on_creation": is_alive(f"www.{e}", False),
            "had_www_on_check": is_alive(f"www.{e}", False),
            "tls_info": tls_info
        }
    else:
        if "tls_info" in entry_data[e] and len(entry_data[e]["tls_info"]) == 0:
            try:
                entry_data[e]['tls_info'] = get_tls_info(e)
            except:
                del entry_data[e]["tls_info"]
        if "times_checked" not in entry_data[e]:
            entry_data[e]["times_checked"] = 0
        if "check_status" not in entry_data[e]:
            domain_is_alive = is_alive(e, True)
            entry_data[e]["check_status"] = domain_is_alive
            entry_data[e]["last_checked"] = current_date
            if domain_is_alive != True:
                entry_data[e]["dead_since"] = current_date
            entry_data[e]["check_counter"] = 0
            entry_data[e]["ever_rechecked"] = True
            entry_data[e]["times_checked"] = 0
            if "ips" not in entry_data[e]:
                entry_data[e]["ips"] = get_ips(e)
        elif "ips" not in entry_data[e]:
            entry_data[e]["ips"] = get_ips(e)
        if entry_data[e]["check_status"] == False:
            dead_domains.append(e)
        if "removed" in entry_data[e]:
            if entry_data[e]["removed"] == True:
                entry_data[e]["readded"] = True
                entry_data[e]["readd"] = current_date
                entry_data[e]["origin_add"] = entry_data[e]["first_seen"]
                entry_data[e]["origin_removed_date"] = entry_data[e]["last_seen"]
        entry_data[e]["last_seen"] = current_date
        entry_data[e]["removed"] = False
        entry_data[e]["removed_date"] = ""
        entry_data[e]["is_valid"] = is_valid(e)
        if "check_counter" not in entry_data[e]:
            entry_data[e]["check_counter"] = random.randint(5, 40)
        if "last_checked" not in entry_data[e]:
            entry_data[e]["last_checked"] = "Unknown"
        entry_data[e]["check_counter"] += 1
        if entry_data[e]["check_status"] == False and "had_www_on_check" not in entry_data[e] and entry_data[e]['check_counter'] > 5:
            entry_data[e]['had_www_on_check'] = is_alive(f"www.{e}", False)
        if entry_data[e]["check_counter"] > 50:
            print(f"Checking {e}...")
            domain_is_alive = is_alive(e, True)
            entry_data[e]["check_status"] = domain_is_alive
            entry_data[e]["last_checked"] = current_date
            entry_data[e]["check_counter"] = 0
            entry_data[e]["ever_rechecked"] = True
            entry_data[e]["times_checked"] += 1
            entry_data[e]['had_www_on_check'] = is_alive(f"www.{e}", False)
            if domain_is_alive != True:
                entry_data[e]["dead_since"] = current_date
                entry_data[e]["check_counter"] = 40
            if e == random_recheck:
                entry_data[e]["check_counter"] += 5
print("Done with part 1")
for e in entry_data:
    if e not in domain_list and e != "last_updated":
        try:
            if "dead_on_removal" in entry_data[e]:
                entry_data[e]['alive_on_removal'] = entry_data[e]["dead_on_removal"]
            if entry_data[e]["removed"] == False:
                entry_data[e]["removed"] = True
                entry_data[e]["removed_date"] = current_date
                entry_data[e]["alive_on_removal"] = is_alive(e)
        except Exception as err:
            print(err, e, entry_data[e])
print("Done with part 2")
entry_data_file = open("entry_data.json", 'w', encoding="UTF-8")
entry_data_file.write(json.dumps(entry_data))
entry_data_file.close()

dead_stuff = open("dead.mwbcheck.txt", 'w', encoding='UTF-8')
dead_stuff.write("\n".join(dead_domains))
dead_stuff.close()