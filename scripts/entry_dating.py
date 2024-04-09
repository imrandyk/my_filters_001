import os, sys, json, datetime, socket, random, publicsuffixlist, ssl
import dns.resolver

dead_domains = []
p = publicsuffixlist.PublicSuffixList(only_icann=True)
resolver = dns.resolver.Resolver()
resolver.nameservers = ["https://unfiltered.adguard-dns.com/dns-query","94.140.14.140", "8.8.8.8","1.1.1.1"]
already_resolved = {}
known_whois = {}

verbosity = 4

def log_msg(msg, level=0):
	elif level > 0 and level > verbosity:
		return
	print(f"[{datetime.datetime.now().isoformat()} - {threading.current_thread().name} - {level}] {msg}")

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

get_whois = None
times_hit_max = 0
def get_whois(domain, server = None, done_whois_servers = [], recurse=False, sub=False):
    global known_whois
    global max_queries
    global times_hit_max
    log_msg(f"Getting WHOIS record for {domain} using {server or 'no server specified'}, recurse is {recurse}", 5)
    if sub == True:
        log_msg("Sleeping for 1", 6)
        time.sleep(1)
        log_msg("Sleep done", 6)
    done_whois_servers.append(server)
    if domain in known_whois and sub == False:
        log_msg("Used cached WHOIS", 5)
        return known_whois[domain]
    if max_queries:
        log_msg("At max queries, not querying right now (waiting 120)", 3)
        time.sleep(120)
    if server == None:
        tld = p.publicsuffix(domain).upper()
        server = f"{tld}.whois-servers.net"
    try:
        whois_data = get_whois_data_raw(domain, server)
    except Exception as err:
        log_msg(f"{server} failed to get WHOIS for {domain} due to {err}", 4)
        time.sleep(1)
        return ""
    if "Number of allowed queries exceeded" in whois_data:
        log_msg(f"Hit max allowed queries (on domain {domain}, server {server}). Hit max {times_hit_max} times before", 2)
        times_hit_max += 1
        max_queries = True
        log_msg(f"Sleeping for {120*times_hit_max}", 6)
        time.sleep(120*times_hit_max)
        log_msg(f"Done sleeping", 6)
        max_queries = False
        return get_whois(domain, server=server, done_whois_servers=done_whois_servers, recurse=recurse, sub=sub)
    if recurse == True:
        try:
            for line in whois_data.replace("\r", "").split("\n"):
                log_msg(line.replace(" ", "").replace("\t", ""), 6)
                if line.replace(" ", "").replace("\t", "").startswith("RegistrarWHOISServer:"):
                    newserver = line.replace(" ", "").replace("\t", "").replace("RegistrarWHOISServer:", "").replace("http://", "").replace("https://", "").split("/")[0]
                    log_msg(f"Fetching more WHOIS data from {newserver}", 5)
                    if newserver not in done_whois_servers:
                        whois_data += "\n" + get_whois(domain, server=newserver, recurse=True, sub=True, done_whois_servers=done_whois_servers)
                    done_whois_servers.append(newserver)
        except Exception as err:
            log_msg(f"Recurse for {domain} ({server}) failed due to {err}", 3)
                    
    if sub == False:
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

def get_last_commit():
    try:
        return requests.get("https://api.github.com/repos/iam-py-test/my_filters_001/commits").json()[0]['html_url']
    except:
        return None

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
last_commit = get_last_commit()
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
            "tls_info": tls_info,
            "last_commit": last_commit
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
        if entry_data[e]["check_counter"] > 45:
            print(f"Checking {e}...", "previous status", entry_data[e]["check_status"], "last check", entry_data[e]["last_checked"])
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
    if e not in domain_list and e != "last_updated" and e != "":
        try:
            if "dead_on_removal" in entry_data[e]:
                entry_data[e]['alive_on_removal'] = entry_data[e]["dead_on_removal"]
            if entry_data[e]["removed"] == False:
                entry_data[e]["removed"] = True
                entry_data[e]["removed_date"] = current_date
                entry_data[e]["alive_on_removal"] = is_alive(e, False)
        except Exception as err:
            print(err, e, entry_data[e])
print("Done with part 2")
entry_data_file = open("entry_data.json", 'w', encoding="UTF-8")
entry_data_file.write(json.dumps(entry_data))
entry_data_file.close()

dead_stuff = open("dead.mwbcheck.txt", 'w', encoding='UTF-8')
dead_stuff.write("\n".join(dead_domains))
dead_stuff.close()