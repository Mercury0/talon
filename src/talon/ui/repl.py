"""Main REPL interface for Talon."""

import json
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Set, List, Optional, Dict, Any

try:
    from requests import RequestException
except ImportError:
    RequestException = Exception

from ..api.client import FalconClient
from ..config.settings import TalonState
from ..models import Connection, AlertFilter, OutputFormat
from ..utils.colors import Fore, Style
from ..utils.spinner import TqdmSpinner
from ..utils.time_helpers import now_utc, fql_time, fmt_ts, parse_iso_utc, pick_created_iso
from .constants import ROOT_HELP_CONNECTED, ROOT_HELP_DISCONNECTED, KEYS_HELP, CONFIG_HELP, HELP_TOPICS, DB_HELP
from .display import generate_conn_id, mask_secret, _returned_to_root
from .selector import select_index
from ..database import AlertsDB


class TalonREPL:
    """Main REPL interface for Talon."""
    
    def __init__(self, state: TalonState):
        self.s = state
        self.alert_id_cache = {}  # Map short IDs to full IDs
        self.alerts_db = AlertsDB()  # Initialize database
        self.new_alerts_count = 0   # Track new alerts in current session

    # ---------- Root REPL ----------
    def root_loop(self):
        """Main REPL loop."""
        while True:
            try:
                # Prompt: white **bold** ">" when disconnected; YELLOW+BOLD "talon [connected] >" when connected
                if self.s.connected:
                    prompt = Fore.YELLOW + Style.BRIGHT + "talon [connected] > " + Style.RESET_ALL
                else:
                    prompt = Fore.WHITE + Style.BRIGHT + "> " + Style.RESET_ALL
                try:
                    line = input(prompt)
                except KeyboardInterrupt:
                    print()
                    _returned_to_root()
                    continue
            except EOFError:
                print()  # clean newline on CTRL+d
                break

            cmd = (line or "").strip()
            if not cmd:
                continue

            try:
                if cmd == "exit":
                    break

                if cmd == "help":
                    print()  # blank line before help block
                    # Print help blocks in terminal default white (no Fore)
                    if self.s.connected:
                        print(ROOT_HELP_CONNECTED)
                    else:
                        print(ROOT_HELP_DISCONNECTED)
                    print()  # extra blank line after help block
                    continue

                if cmd == "connect":
                    self.cmd_connect()
                    continue

                if cmd == "run":
                    self.cmd_run()
                    continue

                if cmd == "config":
                    if not self.s.connected:
                        print("Unknown command. Type 'help'.")
                        continue
                    self.config_loop()
                    continue

                if cmd == "keys":
                    self.keys_loop()
                    continue

                if cmd == "db":
                    self.db_loop()
                    continue

                if cmd.startswith("help "):
                    topic = cmd.split(" ", 1)[1].strip().lower()
                    print()  # blank line before topic help
                    if topic in HELP_TOPICS:
                        print(HELP_TOPICS[topic])
                    elif self.s.connected and topic in ("keys", "config", "run", "exit", "help", "stats", "detail"):
                        print(ROOT_HELP_CONNECTED)
                    elif (not self.s.connected) and topic in ("keys", "connect", "exit", "help", "detail"):
                        print(ROOT_HELP_DISCONNECTED)
                    else:
                        print("No help for that topic.")
                    print()  # extra blank line after topic help
                    continue

                if cmd == "stats":
                    if not self.s.connected:
                        print("Not connected. Use 'connect' first.")
                        continue
                    self.show_stats()
                    continue

                if cmd == "detail":
                    # Allow detail selection without requiring connection
                    self.cmd_detail_select()
                    continue

                if cmd.startswith("detail "):
                    alert_id = cmd.split(" ", 1)[1].strip()
                    # Try to show from database first, fall back to API if connected
                    self.show_alert_detail(alert_id)
                    continue

                print("Unknown command. Type 'help'.")
            except KeyboardInterrupt:
                print()
                _returned_to_root()
                # loop continues to top, showing root prompt

    # ---------- keys submenu ----------
    def keys_loop(self):
        """Keys management submenu."""
        while True:
            try:
                line = input("keys> ")
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                raise  # bubble to root to show the cyan message there

            cmd = (line or "").strip()
            if not cmd:
                continue

            try:
                if cmd == "back":
                    break

                if cmd == "help":
                    print()  # newline before help block
                    print(KEYS_HELP)  # default white
                    print()  # extra blank line after help block
                    continue

                if cmd.startswith("help "):
                    topic = cmd.split(" ", 1)[1].strip().lower()
                    print()  # newline before topic help
                    print(HELP_TOPICS.get(topic, "No help for that topic."))
                    print()  # extra blank line after topic help
                    continue

                if cmd == "create":
                    self.keys_create()
                    continue

                if cmd == "list":
                    self.keys_list()
                    continue

                if cmd == "remove":
                    self.keys_remove()
                    continue

                print("Unknown command. Type 'help'.")
            except KeyboardInterrupt:
                print()
                raise

    def keys_create(self):
        """Create a new connection."""
        try:
            cid = input("Enter Falcon ClientID: ").strip()
            sec = input("Enter Secret: ").strip()
            burl = input("Enter Base URL: ").strip()
        except EOFError:
            print("\nCreate cancelled.")
            return
        except KeyboardInterrupt:
            print()
            raise  # bounce to root

        if not cid or not sec or not burl:
            print("All fields are required.")
            return

        conn_id = generate_conn_id()
        self.s.connections.append(Connection(id=conn_id, client_id=cid, client_secret=sec, base_url=burl))
        print(Fore.YELLOW + Style.BRIGHT + f"Connection [{conn_id}] has been created." + Style.RESET_ALL)
        # Selecting a new active connection invalidates prior session
        self.s.active_id = conn_id
        self.s.client = None
        self.s.connected = False

    def keys_list(self):
        """List and select connections."""
        if not self.s.connections:
            print("(no connections)")
            return
        try:
            opts = [f"[{c.id}]" for c in self.s.connections]
            sel_idx = select_index(opts, title="Connection IDs")
            if sel_idx is None:
                return
            c = self.s.connections[sel_idx]
            print(Fore.YELLOW + Style.BRIGHT + f"Connection [{c.id}] details:" + Style.RESET_ALL)
            print(f"  client_id: {c.client_id}")
            print(f"  client_secret: {mask_secret(c.client_secret)}")
            print(f"  base_url: {c.base_url}")
            print(f"  created_at: {fmt_ts(c.created_at)}")
            # Selecting a different connection invalidates prior session
            prev_id = self.s.active_id
            self.s.active_id = c.id
            if prev_id != c.id:
                self.s.client = None
                self.s.connected = False
        except KeyboardInterrupt:
            raise

    def keys_remove(self):
        """Remove a connection."""
        if not self.s.connections:
            print("(no connections)")
            return
        for idx, c in enumerate(self.s.connections, 1):
            print(f"{idx}. [{c.id}]")
        try:
            sel = input("Remove by number (Enter to cancel): ").strip()
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print()
            raise
        if not sel:
            return
        if not sel.isdigit():
            print("Invalid selection.")
            return
        i = int(sel)
        if i < 1 or i > len(self.s.connections):
            print("Out of range.")
            return
        removed = self.s.connections.pop(i-1)
        print(f"Removed connection [{removed.id}]")
        if self.s.active_id == removed.id:
            self.s.active_id = None
            self.s.connected = False
            self.s.client = None

    # ---------- config submenu (only after connected) ----------
    def config_loop(self):
        """Configuration submenu."""
        while True:
            try:
                line = input("config> ")
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                raise
            cmd = (line or "").strip()
            if not cmd:
                continue

            try:
                if cmd == "back":
                    break

                if cmd == "help":
                    print()  # newline before help block
                    print(CONFIG_HELP)  # default white
                    print()  # extra blank line after help block
                    continue

                if cmd.startswith("help "):
                    topic = cmd.split(" ", 1)[1].strip().lower()
                    print()  # newline before topic help
                    print(HELP_TOPICS.get(topic, "No help for that topic."))
                    print()  # extra blank line after topic help
                    continue

                # Single option: polling -> prompt directly
                if cmd == "polling":
                    try:
                        val = input("Set polling frequency (seconds) [default: 15s]: ").strip()
                    except EOFError:
                        print()
                        continue
                    except KeyboardInterrupt:
                        print()
                        raise
                    if not val:
                        self.s.poll_interval = 15
                        print("[+] polling interval set to 15s")
                        continue
                    try:
                        n = int(val)
                        if n < 1:
                            print("Must be >= 1")
                            continue
                        self.s.poll_interval = n
                        print(f"[+] polling interval set to {n}s")
                    except ValueError:
                        print("Must be an integer")
                    continue

                if cmd == "filter":
                    try:
                        print("Current filter settings:")
                        f = self.s.alert_filter
                        print(f"  Severity min: {f.severity_min or 'none'}")
                        print(f"  Product: {f.product or 'any'}")
                        print(f"  Hostname: {f.hostname or 'any'}")
                        print(f"  Status: {f.status or 'any'}")
                        print(f"  Keywords: {', '.join(f.keywords) if f.keywords else 'none'}")
                        print()
                        
                        choice = input("Configure [s]everity/[p]roduct/[h]ostname/s[t]atus/[k]eywords/[c]lear/[q]uit: ").strip().lower()
                        
                        if choice == 's':
                            val = input("Minimum severity (empty to clear): ").strip()
                            if val:
                                try:
                                    self.s.alert_filter.severity_min = int(val)
                                    print(f"[+] Minimum severity set to {val}")
                                except ValueError:
                                    print("Must be a number")
                            else:
                                self.s.alert_filter.severity_min = None
                                print("[+] Severity filter cleared")
                        elif choice == 'p':
                            val = input("Product filter (empty to clear): ").strip()
                            self.s.alert_filter.product = val if val else None
                            print(f"[+] Product filter {'set to ' + val if val else 'cleared'}")
                        elif choice == 'h':
                            val = input("Hostname filter (empty to clear): ").strip()
                            self.s.alert_filter.hostname = val if val else None
                            print(f"[+] Hostname filter {'set to ' + val if val else 'cleared'}")
                        elif choice == 't':
                            val = input("Status filter (empty to clear): ").strip()
                            self.s.alert_filter.status = val if val else None
                            print(f"[+] Status filter {'set to ' + val if val else 'cleared'}")
                        elif choice == 'k':
                            val = input("Keywords (comma-separated, empty to clear): ").strip()
                            if val:
                                self.s.alert_filter.keywords = [k.strip() for k in val.split(',') if k.strip()]
                                print(f"[+] Keywords set to: {', '.join(self.s.alert_filter.keywords)}")
                            else:
                                self.s.alert_filter.keywords = []
                                print("[+] Keywords cleared")
                        elif choice == 'c':
                            from ..models.filters import AlertFilter
                            self.s.alert_filter = AlertFilter()
                            print("[+] All filters cleared")
                        
                    except (EOFError, KeyboardInterrupt):
                        print()
                        if isinstance(sys.exc_info()[1], KeyboardInterrupt):
                            raise
                    continue

                if cmd == "lookback":
                    try:
                        val = input("Set lookback range in minutes [default: 10]: ").strip()
                        if not val:
                            self.s.lookback_minutes = 10
                            print("[+] Lookback set to 10 minutes")
                        else:
                            try:
                                n = int(val)
                                if n < 1:
                                    print("Must be >= 1 minute")
                                    continue
                                self.s.lookback_minutes = n
                                print(f"[+] Lookback set to {n} minutes")
                            except ValueError:
                                print("Must be an integer")
                    except (EOFError, KeyboardInterrupt):
                        print()
                        if isinstance(sys.exc_info()[1], KeyboardInterrupt):
                            raise
                    continue

                # Add other config options here...
                print("Unknown command. Type 'help'.")
            except KeyboardInterrupt:
                print()
                raise

    # ---------- connect (auth; shows bright-white tqdm spinner that disappears) ----------
    def cmd_connect(self):
        """Connect to Falcon API."""
        conn = self.s.active()
        if not conn:
            print("No active connection. Use 'keys' -> 'create' or 'list' to select one.")
            return

        # Ensure client is set for the selected connection
        if not self.s.client or \
           self.s.client.client_id != conn.client_id or \
           self.s.client.client_secret != conn.client_secret or \
           self.s.client.base_url != conn.base_url:
            self.s.client = FalconClient(conn.base_url, conn.client_id, conn.client_secret)

        client = self.s.client

        # Authenticate only if token not valid yet
        show_auth = not client.is_token_valid()
        if show_auth:
            spinner = TqdmSpinner(message="Authenticating…", interval=0.08)
            spinner.start()
            try:
                client.token()
            except RequestException:
                spinner.stop()
                print(Fore.RED + "Auth failure" + Style.RESET_ALL)
                return
            except Exception:
                spinner.stop()
                print(Fore.RED + "Auth failure" + Style.RESET_ALL)
                return
            spinner.stop()

        # Mark connected
        was_connected = self.s.connected
        self.s.connected = True

        # Only show confirmation if we just connected or refreshed token
        if (not was_connected) or show_auth:
            print(Fore.YELLOW + Style.BRIGHT + "talon [connected]" + Style.RESET_ALL)

        # Start watcher
        self._watch(client)

    # ---------- run (no auth; requires an existing connection) ----------
    def cmd_run(self):
        """Run alert monitoring without re-authenticating."""
        if not self.s.connected or not self.s.client:
            print("Not connected. Use 'connect' first.")
            return
        # Just start the watcher without any auth message
        self._watch(self.s.client)

    # ---------- watcher loop ----------
    def _watch(self, client: FalconClient):
        """Main alert watching loop."""
        # Start with last 10 minutes of *created* alerts, then only newly created ones.
        lookback_min = self.s.lookback_minutes
        created_since_dt = now_utc() - timedelta(minutes=lookback_min)
        last_created_iso = fql_time(created_since_dt)
        seen_ids: Set[str] = set()

        print(f"[+] Watching alerts since {fmt_ts(created_since_dt)} (poll {self.s.poll_interval}s)…")
        # Bold yellow for the CTRL+C hint
        print(Fore.YELLOW + Style.BRIGHT + "(Press CTRL+C to stop watching and return to the menu)" + Style.RESET_ALL)

        try:
            while True:
                try:
                    ids = client.query_alert_ids(last_created_iso)
                    if ids:
                        # De-dupe IDs in case of any overlap
                        ids = [i for i in ids if i not in seen_ids]
                        if ids:
                            alerts = client.fetch_alerts(ids)
                            # Sort by created time so we advance watermark in order
                            def _sort_key(a):
                                return pick_created_iso(a) or ""
                            alerts.sort(key=_sort_key)

                            max_created_seen = None
                            for a in alerts:
                                aid_full = a.get("composite_id") or a.get("id") or "unknown-id"
                                if ':ind:' in aid_full:
                                    aid = aid_full[aid_full.find('ind:'):]  # Extract display ID
                                elif ':det:' in aid_full:
                                    aid = aid_full[aid_full.find('det:'):]  # Extract from 'det:' onwards
                                else:
                                    aid = aid_full
                                # Store the ORIGINAL full ID, not the extracted one
                                self.alert_id_cache[aid] = aid_full  # This should be the original API response ID
                                if aid in seen_ids:
                                    continue  # hard de-dupe
                                
                                # Apply filters
                                if not self.s.matches_filter(a, self.s.alert_filter):
                                    continue

                                # Update stats
                                self.s.alert_stats.add_alert(a)
                                
                                created_iso = pick_created_iso(a)
                                ts_h = fmt_ts(parse_iso_utc(created_iso)) if created_iso else "-"

                                name = a.get("name") or a.get("title") or a.get("display_name") or "Alert"
                                sev = a.get("severity", "")
                                stat = str(a.get("status", ""))

                                # product label (green); try several fields, uppercase; fallback to UNKNOWN
                                prod_raw = a.get("product") or a.get("source") or a.get("category")
                                prod_label = str(prod_raw).strip().upper() if prod_raw else "UNKNOWN"
                                product_tag = f" [{Fore.GREEN}{prod_label}{Style.RESET_ALL}]"

                                host = None
                                dev = a.get("device")
                                if isinstance(dev, dict):
                                    host = dev.get("hostname")

                                # severity color (handle numeric/string)
                                sev_str = str(sev)
                                sev_upper = sev_str.upper()
                                try:
                                    sev_int = int(sev_str)
                                except Exception:
                                    sev_int = None

                                if sev_int is not None:
                                    if sev_int >= 60:
                                        sev_col = Fore.RED
                                    elif sev_int >= 30:
                                        sev_col = Fore.BLUE
                                    else:
                                        sev_col = Fore.GREEN
                                else:
                                    if sev_upper in ("CRITICAL", "HIGH"):
                                        sev_col = Fore.RED
                                    elif sev_upper in ("MEDIUM",):
                                        sev_col = Fore.BLUE
                                    else:
                                        sev_col = Fore.GREEN

                                line = (
                                    f"[{ts_h}]{product_tag} "
                                    f"sev={sev_col}{sev_str}{Style.RESET_ALL} "
                                    f"status={Fore.YELLOW}{Style.BRIGHT}{stat}{Style.RESET_ALL} "
                                    f"id={Fore.BLUE}{aid}{Style.RESET_ALL} "
                                    f"host={Fore.CYAN}{(host or '-')}{Style.RESET_ALL} :: "
                                    f"{Style.BRIGHT}{name}{Style.RESET_ALL}"
                                )
                                
                                # Output handling
                                if self.s.output_format == OutputFormat.JSON:
                                    print(json.dumps(a))
                                else:
                                    print(line)
                                
                                # Store in database and count if new
                                is_new = self.alerts_db.store_alert(a, aid, aid_full)
                                if is_new:
                                    self.new_alerts_count += 1
                                
                                # Log to file if enabled
                                if self.s.log_file:
                                    try:
                                        with open(self.s.log_file, 'a', encoding='utf-8') as f:
                                            if self.s.output_format == OutputFormat.JSON:
                                                f.write(json.dumps(a) + '\n')
                                            else:
                                                f.write(f"{ts_h} | {line}\n")
                                    except Exception as e:
                                        print(Fore.RED + f"[!] Logging error: {e}" + Style.RESET_ALL)
                                
                                seen_ids.add(aid)

                                if created_iso:
                                    if (max_created_seen is None) or (created_iso > max_created_seen):
                                        max_created_seen = created_iso

                            # Advance watermark to the max created we actually processed
                            if max_created_seen:
                                last_created_iso = max_created_seen

                    time.sleep(self.s.poll_interval)
                except RequestException as e:
                    print(Fore.RED + f"[!] HTTP error: {e}; backing off…" + Style.RESET_ALL)
                    time.sleep(5)
        except KeyboardInterrupt:
            print()
            if self.new_alerts_count > 0:
                print(f"Added {Fore.GREEN}{Style.BRIGHT}{self.new_alerts_count}{Style.RESET_ALL} new detections to the database")
                self.new_alerts_count = 0  # Reset counter
            _returned_to_root()
            return
        except Exception as e:
            print(Fore.RED + f"[!] Error: {e}" + Style.RESET_ALL)
            time.sleep(2)
            _returned_to_root()
            return

    def show_stats(self):
        """Show daily alert statistics from database."""
        from ..utils.time_helpers import now_utc
        
        today = now_utc().strftime("%Y-%m-%d")
        stats = self.alerts_db.get_daily_stats(today)
        
        print(f"\nAlert Statistics ({stats['date']}):")
        print(f"Total alerts: {stats['total']}")
        
        if stats['by_severity']:
            print("\nBy Severity:")
            for sev, count in sorted(stats['by_severity'].items(), reverse=True):
                print(f"  {sev}: {count}")
        
        if stats['by_product']:
            print("\nBy Product:")
            for prod, count in sorted(stats['by_product'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {prod}: {count}")
        print()

    def show_alert_detail(self, alert_id: str):
        """Show detailed information about a specific alert."""
        # First try to get from database
        db_alert = self.alerts_db.get_alert_by_short_id(alert_id)
        
        if db_alert:
            # Display from database (no API call needed)
            self._show_alert_from_data(db_alert, alert_id)
            return
        
        # If not in database and we're connected, try API
        if not self.s.connected or not self.s.client:
            print(f"Alert {alert_id} not found in database and not connected to API")
            return
        
        # Try cache first, then API
        full_alert_id = self._find_full_alert_id(alert_id)
        
        try:
            alerts = self.s.client.fetch_alerts([full_alert_id])
            if not alerts:
                print(f"Alert {alert_id} not found")
                return
            
            alert = alerts[0]
            self._show_alert_from_data(alert, alert_id)
            
        except Exception as e:
            print(f"Error fetching alert details: {e}")

    def _show_alert_from_data(self, alert: dict, alert_id: str):
        """Display alert details from alert data (database or API)."""
        # Header with color-coded severity
        sev = alert.get("severity", 0)
        try:
            sev_int = int(sev)
            if sev_int >= 60:
                sev_color = Fore.RED
            elif sev_int >= 30:
                sev_color = Fore.YELLOW
            else:
                sev_color = Fore.GREEN
        except:
            sev_color = Fore.WHITE
        
        print(f"\n{Style.BRIGHT}Alert Details{Style.RESET_ALL}")
        print("=" * 80)
        print(f"{Style.BRIGHT}ID:{Style.RESET_ALL} {Fore.BLUE}{alert_id}{Style.RESET_ALL}")
        print()
        
        # Basic Information
        print(f"{Style.BRIGHT}BASIC INFORMATION{Style.RESET_ALL}")
        print("-" * 40)
        basic_fields = [
            ("Name", alert.get("name")),
            ("Description", alert.get("description")),
            ("Type", alert.get("type")),
            ("Severity", f"{sev_color}{sev}{Style.RESET_ALL}"),
            ("Status", f"{Fore.YELLOW}{alert.get('status')}{Style.RESET_ALL}"),
            ("Product", f"{Fore.GREEN}{alert.get('product')}{Style.RESET_ALL}"),
            ("Created", self._format_timestamp(alert.get("created_timestamp"))),
            ("Updated", self._format_timestamp(alert.get("updated_timestamp"))),
            ("Confidence", alert.get("confidence")),
        ]
        
        for label, value in basic_fields:
            if value:
                print(f"  {label:12}: {value}")
        print()
        
        # Device Information
        device = alert.get("device", {})
        if isinstance(device, dict) and device:
            print(f"{Style.BRIGHT}DEVICE INFORMATION{Style.RESET_ALL}")
            print("-" * 40)
            device_fields = [
                ("Hostname", device.get("hostname")),
                ("Device ID", device.get("device_id")),
                ("External IP", device.get("external_ip")),
                ("Internal IP", device.get("local_ip")),
                ("MAC Address", device.get("mac_address")),
                ("OS Version", device.get("os_version")),
                ("Domain", device.get("machine_domain")),
                ("Agent Version", device.get("agent_version")),
                ("First Seen", self._format_timestamp(device.get("first_seen"))),
                ("Last Seen", self._format_timestamp(device.get("last_seen"))),
            ]
            
            for label, value in device_fields:
                if value:
                    print(f"  {label:13}: {Fore.CYAN}{value}{Style.RESET_ALL}")
            print()
        
        # Process Information
        processes = alert.get("processes", [])
        if processes:
            print(f"{Style.BRIGHT}⚙️  PROCESS INFORMATION{Style.RESET_ALL}")
            print("-" * 40)
            for i, proc in enumerate(processes[:3]):  # Show first 3 processes
                if isinstance(proc, dict):
                    print(f"  Process {i+1}:")
                    proc_fields = [
                        ("  Command Line", proc.get("command_line")),
                        ("  File Path", proc.get("file_name")),
                        ("  SHA256", proc.get("sha256")),
                        ("  MD5", proc.get("md5")),
                        ("  PID", proc.get("process_id")),
                        ("  Parent PID", proc.get("parent_process_id")),
                        ("  User", proc.get("user_name")),
                    ]
                    
                    for label, value in proc_fields:
                        if value:
                            print(f"    {label:15}: {Fore.MAGENTA}{value}{Style.RESET_ALL}")
                    print()
        
        # File Information
        files = alert.get("files", [])
        if files:
            print(f"{Style.BRIGHT}📁 FILE INFORMATION{Style.RESET_ALL}")
            print("-" * 40)
            for i, file_info in enumerate(files[:3]):  # Show first 3 files
                if isinstance(file_info, dict):
                    print(f"  File {i+1}:")
                    file_fields = [
                        ("  File Path", file_info.get("file_path")),
                        ("  File Name", file_info.get("file_name")),
                        ("  SHA256", file_info.get("sha256")),
                        ("  MD5", file_info.get("md5")),
                        ("  File Size", file_info.get("file_size")),
                        ("  File Type", file_info.get("file_type")),
                        ("  Reputation", file_info.get("reputation")),
                    ]
                    
                    for label, value in file_fields:
                        if value:
                            color = Fore.RED if label == "  Reputation" and str(value).lower() in ["malicious", "suspicious"] else Fore.MAGENTA
                            print(f"    {label:15}: {color}{value}{Style.RESET_ALL}")
                    print()
        
        # Network Information
        network = alert.get("network", {})
        if isinstance(network, dict) and network:
            print(f"{Style.BRIGHT}🌐 NETWORK INFORMATION{Style.RESET_ALL}")
            print("-" * 40)
            network_fields = [
                ("Remote IP", network.get("remote_ip")),
                ("Remote Port", network.get("remote_port")),
                ("Local IP", network.get("local_ip")),
                ("Local Port", network.get("local_port")),
                ("Protocol", network.get("protocol")),
                ("Domain", network.get("domain")),
                ("URL", network.get("url")),
            ]
            
            for label, value in network_fields:
                if value:
                    print(f"  {label:12}: {Fore.CYAN}{value}{Style.RESET_ALL}")
            print()
        
        # Raw Behaviors/Techniques
        behaviors = alert.get("behaviors", [])
        if behaviors:
            print(f"{Style.BRIGHT}🎯 BEHAVIORS & TECHNIQUES{Style.RESET_ALL}")
            print("-" * 40)
            for behavior in behaviors[:5]:  # Show first 5 behaviors
                if isinstance(behavior, dict):
                    technique = behavior.get("technique")
                    tactic = behavior.get("tactic")
                    description = behavior.get("description")
                    
                    if technique:
                        print(f"  • {Fore.RED}{technique}{Style.RESET_ALL}: {description or 'No description'}")
                    if tactic:
                        print(f"    Tactic: {Fore.YELLOW}{tactic}{Style.RESET_ALL}")
                    
                    # Display any MITRE IDs
                    mitre_attack = behavior.get("mitre_attack", {})
                    if isinstance(mitre_attack, dict):
                        technique_id = mitre_attack.get("technique_id")
                        tactic_id = mitre_attack.get("tactic_id")
                        if technique_id:
                            print(f"    MITRE Technique: {Fore.BLUE}{technique_id}{Style.RESET_ALL}")
                        if tactic_id:
                            print(f"    MITRE Tactic: {Fore.BLUE}{tactic_id}{Style.RESET_ALL}")
                    print()
        
        # User Information
        user_info = alert.get("user", {})
        if isinstance(user_info, dict) and user_info:
            print(f"{Style.BRIGHT}👤 USER INFORMATION{Style.RESET_ALL}")
            print("-" * 40)
            user_fields = [
                ("Username", user_info.get("user_name")),
                ("Domain", user_info.get("domain")),
                ("SID", user_info.get("sid")),
                ("Privileges", user_info.get("privileges")),
            ]
            
            for label, value in user_fields:
                if value:
                    print(f"  {label:12}: {Fore.CYAN}{value}{Style.RESET_ALL}")
            print()
        
        # Additional Context
        self._display_additional_context(alert)
        
        print("=" * 80)
        print()

    def _format_timestamp(self, timestamp):
        """Format timestamp for display."""
        if not timestamp:
            return None
        try:
            dt = parse_iso_utc(timestamp)
            return fmt_ts(dt)
        except:
            return timestamp

    def _display_additional_context(self, alert):
        """Display additional contextual information."""
        print(f"{Style.BRIGHT}ADDITIONAL CONTEXT{Style.RESET_ALL}")
        print("-" * 40)
        
        # Risk score and confidence
        confidence = alert.get("confidence")
        if confidence:
            conf_color = Fore.RED if int(confidence) > 80 else Fore.YELLOW if int(confidence) > 50 else Fore.GREEN
            print(f"  Confidence: {conf_color}{confidence}%{Style.RESET_ALL}")
        
        # Tags
        tags = alert.get("tags", [])
        if tags:
            print(f"  Tags: {', '.join([f'{Fore.CYAN}{tag}{Style.RESET_ALL}' for tag in tags])}")
        
        # Show any custom IOCs or indicators
        iocs = alert.get("iocs", [])
        if iocs:
            print("  IOCs:")
            for ioc in iocs[:5]:  # Show first 5 IOCs
                if isinstance(ioc, dict):
                    ioc_type = ioc.get("type", "Unknown")
                    ioc_value = ioc.get("value", "")
                    print(f"    • {Fore.RED}{ioc_type}{Style.RESET_ALL}: {ioc_value}")
        
        # Parent/related alerts
        parent_id = alert.get("parent_cid")
        if parent_id:
            print(f"  Parent Alert: {Fore.BLUE}{parent_id}{Style.RESET_ALL}")
        
        print()

    def _find_full_alert_id(self, alert_id: str) -> str:
        """Find the full alert ID for a given alert ID."""
        if alert_id in self.alert_id_cache:
            return self.alert_id_cache[alert_id]
        return alert_id

    def cmd_detail_select(self):
        """Allow user to select from recent alerts."""
        recent_alerts = self.alerts_db.get_recent_alerts(20)
        
        if not recent_alerts:
            print("No alerts found in database")
            return
        
        options = []
        for i, alert in enumerate(recent_alerts, 1):
            sev = alert.get('severity', 0)
            sev_color = Fore.RED if sev >= 60 else Fore.YELLOW if sev >= 30 else Fore.GREEN
            
            created = alert.get('created_timestamp', '')
            if created:
                try:
                    from ..utils.time_helpers import parse_iso_utc, fmt_ts
                    dt = parse_iso_utc(created)
                    time_str = fmt_ts(dt)
                except:
                    time_str = created[:16] if len(created) > 16 else created
            else:
                time_str = 'Unknown'
            
            name = alert.get('name', 'Unknown')[:40]  # Truncate long names
            hostname = alert.get('hostname', '-')
            
            option_text = f"[{time_str}] sev={sev_color}{sev}{Style.RESET_ALL} {hostname} :: {name}"
            options.append(option_text)
        
        from .selector import select_index
        selected_idx = select_index(options, title="Select alert for details")
        
        if selected_idx is not None:
            selected_alert = recent_alerts[selected_idx]
            self.show_alert_detail(selected_alert['short_id'])

    def db_loop(self):
        """Database management submenu."""
        while True:
            try:
                line = input("db> ")
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                raise
            
            cmd = (line or "").strip()
            if not cmd:
                continue

            try:
                if cmd == "back":
                    break

                if cmd == "help":
                    print()
                    print(DB_HELP)
                    print()
                    continue

                if cmd.startswith("help "):
                    topic = cmd.split(" ", 1)[1].strip().lower()
                    print()
                    print(HELP_TOPICS.get(topic, "No help for that topic."))
                    print()
                    continue

                if cmd == "detections":
                    self.cmd_detail_select()  # Reuse existing detection selection
                    continue

                if cmd == "purge":
                    self.db_purge()
                    continue

                if cmd == "export":
                    self.db_export()
                    continue

                print("Unknown command. Type 'help'.")
            except KeyboardInterrupt:
                print()
                raise

    def db_purge(self):
        """Purge all alerts from database."""
        try:
            confirm = input("Are you sure you want to delete ALL stored detections? (yes/no): ").strip().lower()
            if confirm in ('yes', 'y'):
                count = self.alerts_db.purge_alerts()
                print(f"{Fore.GREEN}Deleted {count} detections from database{Style.RESET_ALL}")
            else:
                print("Purge cancelled.")
        except (EOFError, KeyboardInterrupt):
            print("\nPurge cancelled.")

    def db_export(self):
        """Export alerts with format selection."""
        from .selector import select_index
        from pathlib import Path
        
        options = ["CSV format", "JSON format"]
        selected_idx = select_index(options, title="Export format")
        
        if selected_idx is None:
            return
        
        format_type = "csv" if selected_idx == 0 else "json"
        
        try:
            # Use simple default filename
            filename = f"db.{format_type}"
            output_path = Path(filename)
            
            if format_type == "csv":
                count = self.alerts_db.export_alerts_csv(output_path)
            else:
                count = self.alerts_db.export_alerts_json(output_path)
            
            # Clear any cursor positioning issues and print at start of line
            print(f"\r{Fore.YELLOW}{Style.BRIGHT}[+]{Style.RESET_ALL} {filename} saved to current directory")
            
        except (EOFError, KeyboardInterrupt):
            print("\nExport cancelled.")
        except Exception as e:
            print(f"{Fore.RED}Export failed: {e}{Style.RESET_ALL}")
