"""
従業員マスタ生成 CLI

Usage:
  python main.py create-master \\
    --salary  給与一覧.csv \\
    --zengin  振込データ.txt \\
    --output  output/employee_master.csv

  python main.py create-master --help
"""
import argparse
import sys

from src.employee_master import EmployeeMasterCreator


def cmd_create_master(args: argparse.Namespace) -> int:
    print(f"給与CSV:   {args.salary}")
    print(f"全銀データ: {args.zengin}")
    print(f"出力先:    {args.output}")
    print()

    creator = EmployeeMasterCreator(
        salary_csv_path=args.salary,
        zengin_txt_path=args.zengin,
    )

    try:
        master_records, warnings = creator.save(args.output)
    except ValueError as e:
        print(f"[エラー] {e}", file=sys.stderr)
        return 1

    for w in warnings:
        print(w)

    print()
    print(f"完了: {len(master_records)} 件のマスタレコードを {args.output} に出力しました。")
    if warnings:
        print(f"警告: {len(warnings)} 件 — 上記メッセージを確認してください。")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="backoffice",
        description="バックオフィス業務支援ツール",
    )
    subparsers = parser.add_subparsers(dest="command")

    # create-master サブコマンド
    master_parser = subparsers.add_parser(
        "create-master",
        help="給与CSVと全銀データから従業員マスタを生成する",
    )
    master_parser.add_argument("--salary", required=True, metavar="FILE", help="給与一覧CSVファイルのパス")
    master_parser.add_argument("--zengin", required=True, metavar="FILE", help="全銀データ（.txt）ファイルのパス")
    master_parser.add_argument(
        "--output",
        default="output/employee_master.csv",
        metavar="FILE",
        help="出力CSVファイルのパス（デフォルト: output/employee_master.csv）",
    )

    args = parser.parse_args()

    if args.command == "create-master":
        return cmd_create_master(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
