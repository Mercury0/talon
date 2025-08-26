"""Main REPL interface for Talon."""

import json
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Set

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
from .constants import ROOT_HELP_CONNECTED, ROOT_HELP_DISCONNECTED, KEYS_HELP, CONFIG_HELP, HELP_TOPICS
from .display import generate_conn_id, mask_secret, _returned_to_root
from .selector import select_index


class TalonREPL:
    """Main REPL interface for Talon."""
    
    def __init__(self, state: TalonState):
        self.s = state

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

                if cmd.startswith("help "):
                    topic = cmd.split(" ", 1)[1].strip().lower()
                    print()  # blank line before topic help
                    if self.s.connected and topic in ("keys", "config", "run", "exit", "help"):
                        print(ROOT_HELP_CONNECTED)
                    elif (not self.s.connected) and topic in ("keys", "connect", "exit", "help"):
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

                if cmd.startswith("detail "):
                    alert_id = cmd.split(" ", 1)[1].strip()
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

                if cmd == "output":
                    try:
                        fmt = input("Output format [console/json/csv]: ").strip().lower()
                        if fmt in ["console", "json", "csv"]:
                            self.s.output_format = OutputFormat(fmt)
                            print(f"[+] Output format set to {fmt}")
                        else:
                            print("Invalid format")
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
        lookback_min = 10
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
                                aid = a.get("id") or a.get("composite_id") or "unknown-id"
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
            _returned_to_root()
            return
        except Exception as e:
            print(Fore.RED + f"[!] Error: {e}" + Style.RESET_ALL)
            time.sleep(2)
            _returned_to_root()
            return

    def show_stats(self):
        """Show alert statistics."""
        stats = self.s.alert_stats
        print(f"\n📊 Alert Statistics (since {fmt_ts(stats.last_reset)}):")
        print(f"Total alerts: {stats.total_alerts}")
        
        if stats.alerts_by_severity:
            print("\nBy Severity:")
            for sev, count in sorted(stats.alerts_by_severity.items()):
                print(f"  {sev}: {count}")
        
        if stats.alerts_by_product:
            print("\nBy Product:")
            for prod, count in sorted(stats.alerts_by_product.items()):
                print(f"  {prod}: {count}")
        print()

    def show_alert_detail(self, alert_id: str):
        """Show detailed information about a specific alert."""
        try:
            alerts = self.s.client.fetch_alerts([alert_id])
            if not alerts:
                print(f"Alert {alert_id} not found")
                return
            
            alert = alerts[0]
            print(f"\n🔍 Alert Details: {alert_id}")
            print("=" * 50)
            
            # Display key fields in organized format
            fields = [
                ("Name", alert.get("name")),
                ("Description", alert.get("description")),
                ("Severity", alert.get("severity")),
                ("Status", alert.get("status")),
                ("Product", alert.get("product")),
                ("Created", alert.get("created_timestamp")),
                ("Updated", alert.get("updated_timestamp")),
            ]
            
            for label, value in fields:
                if value:
                    print(f"{label:12}: {value}")
            
            # Device info
            device = alert.get("device", {})
            if isinstance(device, dict) and device:
                print(f"{'Hostname':12}: {device.get('hostname', 'N/A')}")
                print(f"{'Device ID':12}: {device.get('device_id', 'N/A')}")
            
            print()
        except Exception as e:
            print(f"Error fetching alert details: {e}")
