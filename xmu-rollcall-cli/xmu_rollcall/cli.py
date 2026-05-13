import click
import sys
from . import __version__
from .proxy_guard import disable_system_proxies

disable_system_proxies()

from xmulogin import xmulogin
from .config import (
    load_config, save_config, is_config_complete, get_cookies_path,
    add_account, get_all_accounts, get_current_account, set_current_account,
    get_account_by_id, CONFIG_FILE, delete_account, perform_account_deletion,
    get_rollcall_settings, set_rollcall_settings, get_notification_settings,
    set_notification_settings,
)
from .notifications_config import DEFAULT_NOTIFICATION_TARGET_ENV
from .colors import Colors
from .monitor import start_monitor, base_url, headers

@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="xmu")
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(f"{Colors.OKCYAN}{Colors.BOLD}XMU Rollcall Bot CLI v{__version__}{Colors.ENDC}")
        click.echo(f"\nUsage:")
        click.echo(f"  xmu config    Configure credentials and add accounts")
        click.echo(f"  xmu switch    Switch between accounts")
        click.echo(f"  xmu start     Start monitoring rollcalls")
        click.echo(f"  xmu refresh   Refresh the login status")
        click.echo(f"  xmu --help    Show this message")
        click.echo(f"  xmu --version Show version")
        click.echo(f"\nNotification target defaults to env var: {DEFAULT_NOTIFICATION_TARGET_ENV}")

@cli.command(help="配置账号、签到安全设置与通知投递")
def config():
    """配置账号：添加、删除账号"""
    click.echo(f"\n{Colors.BOLD}{Colors.OKCYAN}=== XMU Rollcall Configuration ==={Colors.ENDC}\n")

    try:
        current_config = load_config()
    except Exception as e:
        click.echo(f"{Colors.FAIL}Failed to load config: {str(e)}{Colors.ENDC}")
        sys.exit(1)

    def show_accounts():
        """显示账号列表"""
        accounts = get_all_accounts(current_config)
        if accounts:
            click.echo(f"{Colors.BOLD}Existing accounts:{Colors.ENDC}")
            current_account = get_current_account(current_config)
            for acc in accounts:
                current_marker = f" {Colors.OKGREEN}(current){Colors.ENDC}" if current_account and acc.get("id") == current_account.get("id") else ""
                click.echo(f"  {acc.get('id')}: {acc.get('name') or acc.get('username')}{current_marker}")
            click.echo()
        else:
            click.echo(f"{Colors.GRAY}No accounts configured.{Colors.ENDC}\n")

    def add_new_account():
        """添加新账号"""
        click.echo(f"{Colors.BOLD}Adding a new account...{Colors.ENDC}\n")

        # 输入新账号信息
        username = click.prompt(f"{Colors.BOLD}Username{Colors.ENDC}")
        password = click.prompt(f"{Colors.BOLD}Password{Colors.ENDC}", hide_input=False)

        # 验证登录
        click.echo(f"\n{Colors.OKCYAN}Validating credentials...{Colors.ENDC}")
        try:
            session = xmulogin(type=3, username=username, password=password)
            if session:
                click.echo(f"{Colors.OKGREEN}✓ Login successful!{Colors.ENDC}")

                # 获取用户姓名
                click.echo(f"{Colors.OKCYAN}Fetching user profile...{Colors.ENDC}")
                try:
                    profile = session.get(f"{base_url}/api/profile", headers=headers, timeout=15).json()
                    name = profile.get("name", "")
                    click.echo(f"{Colors.OKGREEN}✓ Welcome, {name}!{Colors.ENDC}")
                except Exception:
                    click.echo(f"{Colors.WARNING}⚠ Could not fetch profile, using username as name{Colors.ENDC}")
                    name = username

                # 添加账号
                try:
                    account_id = add_account(current_config, username, password, name)
                    save_config(current_config)

                    click.echo(f"{Colors.OKGREEN}✓ Account added successfully! (ID: {account_id}){Colors.ENDC}")
                    click.echo(f"{Colors.GRAY}Configuration file: {CONFIG_FILE}{Colors.ENDC}\n")
                except RuntimeError as e:
                    click.echo(f"{Colors.FAIL}✗ Failed to save configuration: {str(e)}{Colors.ENDC}")
                    click.echo(f"{Colors.WARNING}Tip: In sandboxed environments (like a-Shell), set environment variable:{Colors.ENDC}")
                    click.echo(f"  export XMU_ROLLCALL_CONFIG_DIR=~/Documents/.xmu_rollcall")
            else:
                click.echo(f"{Colors.FAIL}✗ Login failed. Please check your credentials.{Colors.ENDC}")
        except Exception as e:
            click.echo(f"{Colors.FAIL}✗ Error during login validation: {str(e)}{Colors.ENDC}")

    def delete_existing_account():
        """删除账号"""
        accounts = get_all_accounts(current_config)
        if not accounts:
            click.echo(f"{Colors.WARNING}No accounts to delete.{Colors.ENDC}\n")
            return

        show_accounts()

        # 让用户选择要删除的账号
        valid_ids = [str(acc.get("id")) for acc in accounts]
        selected_id = click.prompt(
            f"{Colors.BOLD}Enter account ID to delete{Colors.ENDC}",
            type=click.Choice(valid_ids, case_sensitive=False)
        )

        selected_id = int(selected_id)
        selected_account = get_account_by_id(current_config, selected_id)

        if selected_account:
            # 确认删除
            confirm = click.prompt(
                f"{Colors.WARNING}Are you sure you want to delete account '{selected_account.get('name') or selected_account.get('username')}' (ID: {selected_id})?{Colors.ENDC}",
                type=click.Choice(['y', 'n'], case_sensitive=False),
                default='n'
            )

            if confirm.lower() == 'y':
                # 执行删除
                success, cookies_to_delete, cookies_to_rename = delete_account(current_config, selected_id)

                if success:
                    # 保存配置
                    save_config(current_config)

                    # 处理cookies文件
                    perform_account_deletion(cookies_to_delete, cookies_to_rename)

                    click.echo(f"{Colors.OKGREEN}✓ Account deleted successfully!{Colors.ENDC}")

                    # 显示ID变更提示
                    if cookies_to_rename:
                        click.echo(f"{Colors.GRAY}Note: Account IDs have been re-assigned.{Colors.ENDC}")
                    click.echo()
                else:
                    click.echo(f"{Colors.FAIL}✗ Failed to delete account.{Colors.ENDC}\n")
            else:
                click.echo(f"{Colors.GRAY}Deletion cancelled.{Colors.ENDC}\n")
        else:
            click.echo(f"{Colors.FAIL}✗ Account not found.{Colors.ENDC}\n")

    # 主循环
    def configure_rollcall_settings():
        accounts = get_all_accounts(current_config)
        if not accounts:
            click.echo(f"{Colors.WARNING}No accounts configured.{Colors.ENDC}\n")
            return

        show_accounts()
        valid_ids = [str(acc.get("id")) for acc in accounts]
        selected_id = click.prompt(
            f"{Colors.BOLD}Enter account ID to configure{Colors.ENDC}",
            type=click.Choice(valid_ids, case_sensitive=False)
        )

        account = get_account_by_id(current_config, int(selected_id))
        settings = get_rollcall_settings(account)

        click.echo(f"\n{Colors.BOLD}Rollcall safety settings:{Colors.ENDC}")
        click.echo(f"  Number rollcall delay: {settings['number_delay_min']} - {settings['number_delay_max']} seconds")
        click.echo(f"  Radar rollcall delay: {settings.get('radar_delay_min', 0)} - {settings.get('radar_delay_max', 0)} seconds")
        click.echo(f"  Manual confirm before answering: {'yes' if settings['manual_confirm'] else 'no'}")
        mode = settings.get('wait_before_answer_mode', 'none')
        if mode == 'fixed':
            click.echo(f"  Wait for classmates: fixed {settings.get('wait_before_answer_count_min', 0)} students")
        elif mode == 'random':
            click.echo(f"  Wait for classmates: random {settings.get('wait_before_answer_count_min', 0)}-{settings.get('wait_before_answer_count_max', 0)} students")
        else:
            click.echo(f"  Wait for classmates: no wait")
        click.echo()

        delay_min = click.prompt(
            f"{Colors.BOLD}Minimum delay before number rollcall answer (seconds){Colors.ENDC}",
            type=int,
            default=settings["number_delay_min"]
        )
        delay_max = click.prompt(
            f"{Colors.BOLD}Maximum delay before number rollcall answer (seconds){Colors.ENDC}",
            type=int,
            default=max(settings["number_delay_max"], delay_min)
        )
        radar_delay_min = click.prompt(
            f"{Colors.BOLD}Minimum delay before radar rollcall answer (seconds){Colors.ENDC}",
            type=int,
            default=settings.get("radar_delay_min", 0)
        )
        radar_delay_max = click.prompt(
            f"{Colors.BOLD}Maximum delay before radar rollcall answer (seconds){Colors.ENDC}",
            type=int,
            default=max(settings.get("radar_delay_max", 0), radar_delay_min)
        )

        # Wait before answer strategy
        click.echo(f"\n{Colors.BOLD}Wait for classmates before answering?{Colors.ENDC}")
        click.echo(f"  1) No wait (answer immediately after delay)")
        click.echo(f"  2) Fixed - wait until N students have answered")
        click.echo(f"  3) Random - wait until a random number (0-N) of students have answered")
        current_mode = settings.get('wait_before_answer_mode', 'none')
        mode_default = {'none': '1', 'fixed': '2', 'random': '3'}.get(current_mode, '1')
        wait_mode_choice = click.prompt(
            f"{Colors.BOLD}Choice{Colors.ENDC}",
            type=click.Choice(['1', '2', '3'], case_sensitive=False),
            default=mode_default
        )
        mode_map = {'1': 'none', '2': 'fixed', '3': 'random'}
        wait_mode = mode_map[wait_mode_choice]

        wait_count_min = settings.get('wait_before_answer_count_min', 0)
        wait_count_max = settings.get('wait_before_answer_count_max', 0)
        if wait_mode == 'fixed':
            wait_count_min = click.prompt(
                f"{Colors.BOLD}How many classmates to wait for{Colors.ENDC}",
                type=int,
                default=wait_count_min
            )
            wait_count_max = wait_count_min
        elif wait_mode == 'random':
            wait_count_min = click.prompt(
                f"{Colors.BOLD}Minimum classmates to wait for{Colors.ENDC}",
                type=int,
                default=wait_count_min
            )
            wait_count_max = click.prompt(
                f"{Colors.BOLD}Maximum classmates to wait for{Colors.ENDC}",
                type=int,
                default=max(wait_count_max, wait_count_min)
            )

        manual_confirm = click.confirm(
            f"{Colors.BOLD}Require manual confirmation before answering rollcalls?{Colors.ENDC}",
            default=settings["manual_confirm"]
        )

        set_rollcall_settings(account, {
            "number_delay_min": delay_min,
            "number_delay_max": delay_max,
            "radar_delay_min": radar_delay_min,
            "radar_delay_max": radar_delay_max,
            "manual_confirm": manual_confirm,
            "wait_before_answer_mode": wait_mode,
            "wait_before_answer_count_min": wait_count_min,
            "wait_before_answer_count_max": wait_count_max,
        })
        save_config(current_config)
        updated = get_rollcall_settings(account)

        click.echo(f"\n{Colors.OKGREEN}Settings saved.{Colors.ENDC}")
        click.echo(f"{Colors.GRAY}Number rollcall delay: {updated['number_delay_min']} - {updated['number_delay_max']} seconds{Colors.ENDC}")
        click.echo(f"{Colors.GRAY}Radar rollcall delay: {updated['radar_delay_min']} - {updated['radar_delay_max']} seconds{Colors.ENDC}")
        click.echo(f"{Colors.GRAY}Manual confirm: {'yes' if updated['manual_confirm'] else 'no'}{Colors.ENDC}")
        wmode = updated.get('wait_before_answer_mode', 'none')
        if wmode == 'fixed':
            click.echo(f"{Colors.GRAY}Wait for classmates: fixed {updated.get('wait_before_answer_count_min', 0)} students{Colors.ENDC}")
        elif wmode == 'random':
            click.echo(f"{Colors.GRAY}Wait for classmates: random {updated.get('wait_before_answer_count_min', 0)}-{updated.get('wait_before_answer_count_max', 0)} students{Colors.ENDC}")
        else:
            click.echo(f"{Colors.GRAY}Wait for classmates: no wait{Colors.ENDC}")
        click.echo()

    def configure_notifications():
        accounts = get_all_accounts(current_config)
        if not accounts:
            click.echo(f"{Colors.WARNING}No accounts configured.{Colors.ENDC}\n")
            return

        show_accounts()
        valid_ids = [str(acc.get("id")) for acc in accounts]
        selected_id = click.prompt(
            f"{Colors.BOLD}Enter account ID to configure notifications for{Colors.ENDC}",
            type=click.Choice(valid_ids, case_sensitive=False)
        )

        account = get_account_by_id(current_config, int(selected_id))
        settings = get_notification_settings(account)
        target = settings["target"]

        click.echo(f"\n{Colors.BOLD}Notification settings:{Colors.ENDC}")
        click.echo(f"  Enabled: {'yes' if settings['enabled'] else 'no'}")
        click.echo(f"  Notify on new rollcall: {'yes' if settings['notify_on_new_rollcall'] else 'no'}")
        click.echo(f"  Target mode: {target['type']}")
        click.echo(f"  Target value: {target['value']}\n")

        enabled = click.confirm(
            f"{Colors.BOLD}Enable notifications for this account?{Colors.ENDC}",
            default=settings["enabled"]
        )
        notify_on_new_rollcall = click.confirm(
            f"{Colors.BOLD}Send a message as soon as a new rollcall is detected?{Colors.ENDC}",
            default=settings["notify_on_new_rollcall"]
        )
        target_mode = click.prompt(
            f"{Colors.BOLD}Notification target mode (env/fixed){Colors.ENDC}",
            type=click.Choice(['env', 'fixed'], case_sensitive=False),
            default=target["type"]
        ).lower()
        default_target_value = target["value"] if target_mode == target["type"] else (
            DEFAULT_NOTIFICATION_TARGET_ENV if target_mode == 'env' else ''
        )
        target_value = click.prompt(
            f"{Colors.BOLD}Notification target {'environment variable name' if target_mode == 'env' else 'direct target value'}{Colors.ENDC}",
            default=default_target_value,
            show_default=True
        )

        set_notification_settings(account, {
            "enabled": enabled,
            "notify_on_new_rollcall": notify_on_new_rollcall,
            "target": {
                "type": target_mode,
                "value": target_value,
            },
        })
        save_config(current_config)
        updated = get_notification_settings(account)

        click.echo(f"\n{Colors.OKGREEN}Notification settings saved.{Colors.ENDC}")
        click.echo(f"{Colors.GRAY}Enabled: {'yes' if updated['enabled'] else 'no'}{Colors.ENDC}")
        click.echo(f"{Colors.GRAY}Notify on new rollcall: {'yes' if updated['notify_on_new_rollcall'] else 'no'}{Colors.ENDC}")
        click.echo(f"{Colors.GRAY}Target mode: {updated['target']['type']}{Colors.ENDC}")
        click.echo(f"{Colors.GRAY}Target value: {updated['target']['value']}{Colors.ENDC}\n")

    while True:
        show_accounts()

        click.echo(f"{Colors.BOLD}Choose an action:{Colors.ENDC}")
        click.echo(f"  {Colors.OKCYAN}n{Colors.ENDC} - Add new account")
        click.echo(f"  {Colors.OKCYAN}d{Colors.ENDC} - Delete account")
        click.echo(f"  {Colors.OKCYAN}s{Colors.ENDC} - Configure rollcall safety settings")
        click.echo(f"  {Colors.OKCYAN}m{Colors.ENDC} - Configure notification delivery")
        click.echo(f"  {Colors.OKCYAN}q{Colors.ENDC} - Quit")

        action = click.prompt(
            f"\n{Colors.BOLD}Action{Colors.ENDC}",
            type=click.Choice(['n', 'd', 's', 'm', 'q'], case_sensitive=False),
            default='q'
        )

        click.echo()

        if action.lower() == 'n':
            add_new_account()
        elif action.lower() == 'd':
            delete_existing_account()
        elif action.lower() == 's':
            configure_rollcall_settings()
        elif action.lower() == 'm':
            configure_notifications()
        elif action.lower() == 'q':
            # 退出前显示最终账号列表
            accounts = get_all_accounts(current_config)
            if accounts:
                click.echo(f"{Colors.BOLD}Final account list:{Colors.ENDC}")
                current_account = get_current_account(current_config)
                for acc in accounts:
                    current_marker = f" {Colors.OKGREEN}(current){Colors.ENDC}" if current_account and acc.get("id") == current_account.get("id") else ""
                    click.echo(f"  {acc.get('id')}: {acc.get('name') or acc.get('username')}{current_marker}")
                click.echo(f"\n{Colors.GRAY}You can run: {Colors.BOLD}xmu switch{Colors.ENDC} to switch between accounts")
                click.echo(f"{Colors.GRAY}You can run: {Colors.BOLD}xmu start{Colors.ENDC} to start monitoring")
            break

@cli.command()
def start():
    """启动签到监控"""
    # 加载配置
    try:
        config_data = load_config()
    except Exception as e:
        click.echo(f"{Colors.FAIL}Failed to load config: {str(e)}{Colors.ENDC}")
        sys.exit(1)

    # 检查配置是否完整
    if not is_config_complete(config_data):
        click.echo(f"{Colors.FAIL}✗ Configuration incomplete!{Colors.ENDC}")
        click.echo(f"Please run: {Colors.BOLD}xmu config{Colors.ENDC}")
        sys.exit(1)

    # 获取当前账号
    current_account = get_current_account(config_data)
    click.echo(f"{Colors.OKCYAN}Using account: {current_account.get('name') or current_account.get('username')} (ID: {current_account.get('id')}){Colors.ENDC}")

    # 启动监控
    try:
        start_monitor(current_account)
    except KeyboardInterrupt:
        click.echo(f"\n{Colors.WARNING}Shutting down...{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        click.echo(f"\n{Colors.FAIL}Error: {str(e)}{Colors.ENDC}")
        sys.exit(1)

@cli.command()
def refresh():
    """清除当前账号的登录缓存"""
    try:
        config_data = load_config()
    except Exception as e:
        click.echo(f"{Colors.FAIL}Failed to load config: {str(e)}{Colors.ENDC}")
        sys.exit(1)
    current_account = get_current_account(config_data)

    if not current_account:
        click.echo(f"{Colors.FAIL}✗ No account configured!{Colors.ENDC}")
        click.echo(f"Please run: {Colors.BOLD}xmu config{Colors.ENDC}")
        sys.exit(1)

    account_id = current_account.get("id")
    cookies_path = get_cookies_path(account_id)
    try:
        click.echo(f"\n{Colors.WARNING}Deleting cookies for account {account_id} ({current_account.get('name')})...{Colors.ENDC}")
        # delete cookies file
        import os
        if os.path.exists(cookies_path):
            os.remove(cookies_path)
            click.echo(f"{Colors.OKGREEN}✓ Cookies deleted successfully.{Colors.ENDC}")
        else:
            click.echo(f"{Colors.GRAY}No cookies file found to delete.{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        click.echo(f"{Colors.FAIL}✗ Failed to delete cookies: {str(e)}{Colors.ENDC}")
        sys.exit(1)


@cli.command()
def switch():
    """切换当前使用的账号"""
    click.echo(f"\n{Colors.BOLD}{Colors.OKCYAN}=== Switch Account ==={Colors.ENDC}\n")

    try:
        config_data = load_config()
    except Exception as e:
        click.echo(f"{Colors.FAIL}Failed to load config: {str(e)}{Colors.ENDC}")
        sys.exit(1)
    accounts = get_all_accounts(config_data)

    if not accounts:
        click.echo(f"{Colors.FAIL}✗ No accounts configured!{Colors.ENDC}")
        click.echo(f"Please run: {Colors.BOLD}xmu config{Colors.ENDC}")
        sys.exit(1)

    current_account = get_current_account(config_data)
    current_id = current_account.get("id") if current_account else None

    # 显示账号列表
    click.echo(f"{Colors.BOLD}Available accounts:{Colors.ENDC}")
    for acc in accounts:
        current_marker = f" {Colors.OKGREEN}(current){Colors.ENDC}" if acc.get("id") == current_id else ""
        click.echo(f"  {acc.get('id')}: {acc.get('name') or acc.get('username')}{current_marker}")

    click.echo()

    # 让用户选择账号
    valid_ids = [str(acc.get("id")) for acc in accounts]
    selected_id = click.prompt(
        f"{Colors.BOLD}Enter account ID to switch to{Colors.ENDC}",
        type=click.Choice(valid_ids, case_sensitive=False)
    )

    selected_id = int(selected_id)
    selected_account = get_account_by_id(config_data, selected_id)

    if selected_account:
        set_current_account(config_data, selected_id)
        save_config(config_data)
        click.echo(f"\n{Colors.OKGREEN}✓ Switched to account: {selected_account.get('name') or selected_account.get('username')} (ID: {selected_id}){Colors.ENDC}")
        click.echo(f"{Colors.GRAY}You can now run: {Colors.BOLD}xmu start{Colors.ENDC}")
    else:
        click.echo(f"{Colors.FAIL}✗ Account not found!{Colors.ENDC}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
