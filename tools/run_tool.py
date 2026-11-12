# -*- coding: utf-8 -*-
"""
run_tool.py — أداة تشغيل الدوال الشاملة في مشروع عثمانلي (Universal Function Runner)
═════════════════════════════════════════════════════════════════════════════════

أداة سريعة ومرنة تعمل عبر سطر الأوامر حصراً (CLI Flags & JSON) لتشغيل أي دالة أو كلاس
أو مهمة موجودة في أي ملف من ملفات المشروع، مع الحقن التلقائي لجلسة الحساب واتصال اللعبة.

أمثلة الاستخدام (Usage Examples):
  1. تشغيل دالة باسمها فقط مع البحث التلقائي وحقن الاتصال:
     python run_tool.py -e "shook124@gmail.com" -f get_castle_march_capacity

  2. تشغيل مهمة من كلاس محدد وتمرير قاموس باراميترات JSON:
     python run_tool.py -e "user@example.com" -t tasks.gather_2.GatherTask.run --params '{"res_type": 1, "level": 6}'


python tools/run_tool.py -e "shook124@gmail.com" -f get_castle_march_capacity

python run_tool.py -e "burcudemr@gmail.com" -f get_castle_march_capacity  -k chosen_heroes="[5502009,5502006]"

python run_tool.py -e burcudemr@gmail.com -t tools.world_dispatch_army.simulate_world_dispatch --params '{\"instanceType\": 6, \"toPoint\": {\"x\": 497, \"y\": 307}}'



python run_tool.py -e "burcudemr@gmail.com" -f simulate_gather_dispatch -k x=496 -k y=300 -k res_type=1002

  3. تشغيل دالة محلية من قاعدة البيانات أو ملف دون فتح اتصال باللعبة:
     python run_tool.py -t core.database.get_castle -k email="user@example.com" --no-connect

  4. تمرير باراميترات موقعية ومسماة معاً:
     python run_tool.py -e "user@example.com" -f calculate_distance -a "[100, 200, 300, 400]"
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import importlib
import inspect
import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ── ضبط الترميز ومسارات الاستيراد ─────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.session_manager import SessionManager
from game_client import GameConnection, AccountSession


# ═══════════════════════════════════════════════════════════════════════════════
#  محرك البحث والاستكشاف التلقائي للدوال والكلاسات (Discovery Engine)
# ═══════════════════════════════════════════════════════════════════════════════

class DiscoveredTarget:
    def __init__(
        self,
        module_path: str,
        callable_obj: Callable,
        cls_obj: Optional[type] = None,
        method_name: Optional[str] = None,
        is_method: bool = False,
    ):
        self.module_path = module_path
        self.callable_obj = callable_obj
        self.cls_obj = cls_obj
        self.method_name = method_name
        self.is_method = is_method

    @property
    def display_name(self) -> str:
        if self.is_method and self.cls_obj:
            return f"{self.module_path}.{self.cls_obj.__name__}.{self.method_name}"
        return f"{self.module_path}.{getattr(self.callable_obj, '__name__', str(self.callable_obj))}"


def _find_py_files() -> List[str]:
    """جمع ملفات بايثون في المشروع للبحث التلقائي بدون تكرار."""
    seen_paths = set()
    py_files = []
    for root, _, files in os.walk(_ROOT_DIR):
        # تجاهل مجلدات الكاش والبيئة الافتراضية والنسخ الاحتياطية ومجلدات الواجهة الأمامية
        if any(skip in root for skip in ("__pycache__", ".git", ".idea", ".gemini", "venv", "env", "node_modules", "dist", "build", "dashboard")):
            continue
        for f in files:
            if f.endswith(".py") and not f.startswith("."):
                full_path = os.path.normpath(os.path.join(root, f))
                if full_path not in seen_paths:
                    seen_paths.add(full_path)
                    py_files.append(full_path)
    return py_files


def _search_target_in_file(file_path: str, target_name: str) -> List[Tuple[Optional[str], str]]:
    """فحص ملف بايثون عبر شجرة AST للعثور على أي دالة أو ميثود يطابق الاسم المطلوب دون استيراده مسبقاً."""
    matches = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception:
        return []

    for node in tree.body:
        # 1. دالة عامة
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == target_name:
                matches.append((None, node.name))
        # 2. ميثود داخل كلاس
        elif isinstance(node, ast.ClassDef):
            if node.name == target_name:
                matches.append((node.name, "__init__"))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == target_name:
                        matches.append((node.name, item.name))
                    elif f"{node.name}.{item.name}" == target_name:
                        matches.append((node.name, item.name))
    return matches


def discover_target(target_str: str, file_or_mod: Optional[str] = None) -> DiscoveredTarget:
    """
    تحليل واكتشاف الدالة أو الكلاس المستهدف.
    يدعم الصيغ التالية:
      - target_str="tasks.gather_2.GatherTask.run"
      - target_str="tasks/gather_2.py:GatherTask.run"
      - target_str="GatherTask.run"
      - target_str="find_tiles"
      - file_or_mod="tasks.gather_2", target_str="find_tiles"
    """
    clean_target = target_str.strip()
    mod_path = None
    cls_name = None
    func_name = clean_target

    # 1. إذا كان المسار يحتوي على ':' (مثل tasks/gather_2.py:run)
    if ":" in clean_target:
        parts = clean_target.split(":", 1)
        file_or_mod = parts[0].strip()
        func_name = parts[1].strip()

    # 2. إذا حُدد ملف أو موديول صريح
    if file_or_mod:
        mod_candidate = file_or_mod.replace("\\", "/").strip()
        if mod_candidate.endswith(".py"):
            rel = os.path.relpath(mod_candidate, _ROOT_DIR).replace("\\", "/")
            if rel.endswith(".py"):
                rel = rel[:-3]
            mod_path = rel.replace("/", ".")
        else:
            mod_path = mod_candidate

    # 3. إذا كان target_str يحوي نقاطاً كاملة (tasks.gather_2.GatherTask.run)
    if not mod_path and "." in func_name:
        parts = func_name.split(".")
        # محاولة التجربة من أطول بادئة موديول ممكنة
        for i in range(len(parts) - 1, 0, -1):
            candidate_mod = ".".join(parts[:i])
            try:
                mod = importlib.import_module(candidate_mod)
                rem = parts[i:]
                if len(rem) == 1:
                    cls_name = None
                    func_name = rem[0]
                    mod_path = candidate_mod
                    break
                elif len(rem) == 2:
                    cls_name = rem[0]
                    func_name = rem[1]
                    mod_path = candidate_mod
                    break
            except ImportError:
                continue

    # 4. إذا لم يتم التحديد بعد، البحث التلقائي عبر ملفات المشروع
    if not mod_path:
        search_name = func_name
        req_class = None
        if "." in search_name:
            req_class, search_name = search_name.split(".", 1)

        candidates = []
        for fpath in _find_py_files():
            m_list = _search_target_in_file(fpath, search_name)
            for c_name, fn in m_list:
                if req_class and c_name != req_class:
                    continue
                rel = os.path.relpath(fpath, _ROOT_DIR).replace("\\", "/")
                if rel.endswith(".py"):
                    rel = rel[:-3]
                m_path = rel.replace("/", ".")
                cand = (m_path, c_name, fn)
                if cand not in candidates:
                    candidates.append(cand)

        if not candidates:
            raise ValueError(f"❌ لم يتم العثور على أي دالة أو ميثود باسم '{target_str}' في ملفات المشروع!")

        if len(candidates) > 1:
            # إذا وُجد أكثر من تطابق، فلترة التطابقات الدقيقة في مجلد tasks أولاً
            exact_tasks = [c for c in candidates if c[0].startswith("tasks.")]
            if len(exact_tasks) == 1:
                mod_path, cls_name, func_name = exact_tasks[0]
            else:
                lines = [f"  - {c[0]}.{c[1] + '.' if c[1] else ''}{c[2]}" for c in candidates]
                raise ValueError(
                    f"⚠️ تم العثور على أكثر من تطابق لـ '{target_str}'. يرجى تحديد الموديول عبر --target أو -m:\n"
                    + "\n".join(lines)
                )
        else:
            mod_path, cls_name, func_name = candidates[0]

    # 5. استيراد الموديول واستخراج العنصر البرمجي
    module = importlib.import_module(mod_path)

    if cls_name:
        cls_obj = getattr(module, cls_name, None)
        if not cls_obj or not inspect.isclass(cls_obj):
            raise AttributeError(f"❌ الكلاس '{cls_name}' غير موجود في الموديول '{mod_path}'!")
        method_obj = getattr(cls_obj, func_name, None)
        if not method_obj:
            raise AttributeError(f"❌ الميثود '{func_name}' غير موجود في الكلاس '{cls_name}'!")
        return DiscoveredTarget(
            module_path=mod_path,
            callable_obj=method_obj,
            cls_obj=cls_obj,
            method_name=func_name,
            is_method=True,
        )

    # التحقق هل العنصر في الموديول هو كلاس تم طلب ميثود داخله أو دالة
    if hasattr(module, func_name):
        obj = getattr(module, func_name)
        if inspect.isclass(obj):
            # إذا مرر المستخدم اسم الكلاس فقط، استهدف ميثود run إن وجد
            if hasattr(obj, "run"):
                return DiscoveredTarget(
                    module_path=mod_path,
                    callable_obj=getattr(obj, "run"),
                    cls_obj=obj,
                    method_name="run",
                    is_method=True,
                )
            return DiscoveredTarget(
                module_path=mod_path,
                callable_obj=obj,
                cls_obj=obj,
                is_method=False,
            )
        return DiscoveredTarget(
            module_path=mod_path,
            callable_obj=obj,
            cls_obj=None,
            is_method=False,
        )

    raise AttributeError(f"❌ لا يوجد عنصر باسم '{func_name}' في الموديول '{mod_path}'!")


# ═══════════════════════════════════════════════════════════════════════════════
#  إدارة الحسابات وجلسة اللعبة (Account & Session Resolution)
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_account(email_or_id: Optional[str]) -> AccountSession:
    """استرجاع كائن AccountSession للبريد المطلوب أو أول حساب متاح."""
    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        raise RuntimeError("❌ ملف session_cache.json لا يحتوي على أي حسابات مسجلة!")

    if not email_or_id:
        email = next(iter(accounts.keys()))
        return accounts[email]

    clean_term = email_or_id.strip().lower()

    # 1. مطابقة مباشرة بالبريد
    if clean_term in accounts:
        return accounts[clean_term]

    # 2. مطابقة جزئية
    for k, acc in accounts.items():
        if clean_term in k.lower() or (acc.user_id and clean_term == str(acc.user_id).lower()):
            return acc

    # 3. محاولة تسجيل الدخول أو الجلب من قاعدة البيانات SQLite
    acc = sm.get_or_login(clean_term)
    if acc:
        return acc

    available = ", ".join(list(accounts.keys())[:5])
    raise ValueError(f"❌ لم يتم العثور على الحساب '{email_or_id}'! الحسابات المتوفرة: {available}...")


# ═══════════════════════════════════════════════════════════════════════════════
#  تحويل الباراميترات والحقن التلقائي (Parameter Parsing & Injection)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_value(val_str: str) -> Any:
    """تحويل القيم النصية إلى أنواعها الأصلية (int, float, bool, json dict/list)."""
    val_str = val_str.strip()
    lower = val_str.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("none", "null"):
        return None
    if val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
        return int(val_str)
    try:
        if "." in val_str:
            return float(val_str)
    except ValueError:
        pass
    if (val_str.startswith("{") and val_str.endswith("}")) or (val_str.startswith("[") and val_str.endswith("]")):
        try:
            return json.loads(val_str)
        except Exception:
            pass
    return val_str


def parse_cli_parameters(
    raw_params_json: Optional[str],
    raw_args_json: Optional[str],
    raw_kwargs_list: Optional[List[str]],
) -> Tuple[List[Any], Dict[str, Any]]:
    """دمج وتحليل جميع المعاملات الممررة من سطر الأوامر."""
    pos_args: List[Any] = []
    kw_args: Dict[str, Any] = {}

    if raw_args_json:
        try:
            parsed_args = json.loads(raw_args_json)
        except Exception:
            try:
                parsed_args = ast.literal_eval(raw_args_json)
            except Exception as e:
                raise ValueError(f"❌ خطأ في تنسيق JSON للمعاملات الموقعية --args: {e}")
        if isinstance(parsed_args, list):
            pos_args.extend(parsed_args)
        else:
            pos_args.append(parsed_args)

    if raw_params_json:
        try:
            parsed_params = json.loads(raw_params_json)
        except Exception:
            try:
                parsed_params = ast.literal_eval(raw_params_json)
            except Exception as e:
                raise ValueError(f"❌ خطأ في تنسيق JSON للمعاملات المسماة --params: {e}")

        if isinstance(parsed_params, dict):
            kw_args.update(parsed_params)
        else:
            raise ValueError("--params يجب أن يكون كائن JSON (Dictionary)")

    if raw_kwargs_list:
        for item in raw_kwargs_list:
            if "=" in item:
                k, v = item.split("=", 1)
                kw_args[k.strip()] = _parse_value(v)
            else:
                kw_args[item.strip()] = True

    return pos_args, kw_args


def _get_cached_init_data(email: Optional[str] = None) -> Dict[str, Any]:
    """استرجاع بيانات init_data من ملفات docs المخزنة محلياً إذا كان التشغيل بدون اتصال."""
    if not email:
        return {}
    clean_prefix = email.split("@")[0].lower()
    docs_dir = os.path.join(_ROOT_DIR, "docs")
    if os.path.isdir(docs_dir):
        for candidate in (f"{clean_prefix}_live_memory.json", f"{email.lower()}_live_memory.json"):
            path = os.path.join(docs_dir, candidate)
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            return data
                except Exception:
                    pass
    return {}


def needs_network_connection(discovered: DiscoveredTarget) -> bool:
    """فحص ما إذا كانت الدالة أو الكلاس يتطلب اتصال شبكي بلعبة Empire."""
    from tasks.base_task import BaseTask

    if discovered.cls_obj and issubclass(discovered.cls_obj, BaseTask):
        return True

    # فحص توقيع الدالة والكلاس
    targets_to_inspect = [discovered.callable_obj]
    if discovered.cls_obj:
        targets_to_inspect.append(discovered.cls_obj.__init__)

    network_param_keywords = (
        "conn", "connection", "client", "bot", "game_conn", "game_client",
        "conn_or_init", "init_data",
    )
    for target in targets_to_inspect:
        try:
            sig = inspect.signature(target)
            for param_name in sig.parameters.keys():
                pname = param_name.lower()
                if pname in network_param_keywords or pname.startswith("conn") or "connection" in pname:
                    return True
        except Exception:
            pass
    return False


def instantiate_and_bind(
    discovered: DiscoveredTarget,
    pos_args: List[Any],
    kw_args: Dict[str, Any],
    conn: Optional[GameConnection],
    account: AccountSession,
    user_config: Optional[Dict[str, Any]] = None,
) -> Tuple[Callable, List[Any], Dict[str, Any]]:
    """تهيئة الكلاس وحقن كائنات الاتصال والحساب تلقائياً في المعاملات."""
    from tasks.base_task import BaseTask

    callable_to_run = discovered.callable_obj
    final_kwargs = dict(kw_args)
    final_args = list(pos_args)

    # 1. إذا كان الهدف ميثود داخل كلاس
    if discovered.is_method and discovered.cls_obj:
        cls_ = discovered.cls_obj

        # معالجة كلاسات المهام (BaseTask)
        if issubclass(cls_, BaseTask):
            active_conn = conn
            if active_conn is None:
                class _DummyConn:
                    def __init__(self, acc):
                        self.account = acc
                        self.email = acc.email
                        self.uid = acc.user_id
                        self.kingdom_id = 0
                        self.init_data = {}
                        self.cached_packets = {}
                    async def query(self, *a, **k):
                        return {}
                    async def close(self):
                        pass
                active_conn = _DummyConn(account)

            # إذا كان الكلاس مجرداً (مثل BaseTask نفسه)، نصنع صنفاً فرعياً بسيطاً لتجاوز خطأ التجريد
            if inspect.isabstract(cls_):
                class _DynamicConcreteTask(cls_):
                    async def run(self):
                        return None
                instance = _DynamicConcreteTask(active_conn, config=user_config or {})
            else:
                instance = cls_(active_conn, config=user_config or {})
            callable_to_run = getattr(instance, discovered.method_name)

        # معالجة كلاس CastleBot
        elif cls_.__name__ == "CastleBot":
            from bot_manager import CastleBot
            instance = CastleBot(account, config=user_config or {})
            if conn:
                instance.conn = conn
            callable_to_run = getattr(instance, discovered.method_name)

        # كلاس عام آخر
        else:
            init_sig = inspect.signature(cls_.__init__)
            init_kwargs = {}
            for p in init_sig.parameters.values():
                pname = p.name.lower()
                if pname in ("conn", "connection", "client") and conn:
                    init_kwargs[p.name] = conn
                elif pname in ("account", "acc", "session"):
                    init_kwargs[p.name] = account
                elif pname == "email":
                    init_kwargs[p.name] = account.email
                elif p.name in final_kwargs:
                    init_kwargs[p.name] = final_kwargs.pop(p.name)

            if inspect.isabstract(cls_):
                class _DynamicAbstractImpl(cls_):
                    pass
                instance = _DynamicAbstractImpl(**init_kwargs)
            else:
                instance = cls_(**init_kwargs)
            callable_to_run = getattr(instance, discovered.method_name)

    # 2. فحص توقيع الدالة المطلوب تشغيلها وحقن المتغيرات المتاحة
    try:
        sig = inspect.signature(callable_to_run)
        param_names = set(sig.parameters.keys())

        # حقن المتغيرات الذكية إذا كانت موجودة في التوقيع ولم يمررها المستخدم صراحة
        if "conn" in param_names and "conn" not in final_kwargs and conn:
            final_kwargs["conn"] = conn
        if "connection" in param_names and "connection" not in final_kwargs and conn:
            final_kwargs["connection"] = conn
        if "client" in param_names and "client" not in final_kwargs and conn:
            final_kwargs["client"] = conn
        if "account" in param_names and "account" not in final_kwargs:
            final_kwargs["account"] = account
        if "email" in param_names and "email" not in final_kwargs:
            final_kwargs["email"] = account.email
        if "uid" in param_names and "uid" not in final_kwargs:
            final_kwargs["uid"] = getattr(conn, "uid", account.user_id)
        if "user_id" in param_names and "user_id" not in final_kwargs:
            final_kwargs["user_id"] = getattr(conn, "uid", account.user_id)
        if "kingdom_id" in param_names and "kingdom_id" not in final_kwargs and conn:
            final_kwargs["kingdom_id"] = getattr(conn, "kingdom_id", 0)
        if "conn_or_init" in param_names and "conn_or_init" not in final_kwargs:
            if conn:
                final_kwargs["conn_or_init"] = conn
            else:
                final_kwargs["conn_or_init"] = _get_cached_init_data(account.email)
        if "init_data" in param_names and "init_data" not in final_kwargs:
            if conn and getattr(conn, "init_data", None):
                final_kwargs["init_data"] = conn.init_data
            else:
                final_kwargs["init_data"] = _get_cached_init_data(account.email)

        # التحقق من المعاملات الإجبارية الناقصة
        missing_required = []
        for p in sig.parameters.values():
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
                if p.default == inspect.Parameter.empty and p.name not in final_kwargs:
                    # التحقق هل تم تغطيتها بـ pos_args
                    if len(final_args) == 0:
                        missing_required.append(p.name)

        if missing_required:
            raise ValueError(
                f"❌ معاملات إجبارية ناقصة للدالة '{callable_to_run.__name__}': {missing_required}\n"
                f"توقيع الدالة: {sig}\n"
                f"استخدم -k {missing_required[0]}=القيمة أو --params '{{\"{missing_required[0]}\": ...}}'"
            )

    except (ValueError, TypeError):
        raise
    except Exception as e:
        logging.debug(f"Signature check bypass: {e}")

    return callable_to_run, final_args, final_kwargs


# ═══════════════════════════════════════════════════════════════════════════════
#  الدالة الرئيسية والتنفيذ (Main CLI Entrypoint)
# ═══════════════════════════════════════════════════════════════════════════════

async def async_main() -> int:
    parser = argparse.ArgumentParser(
        description="أداة تشغيل الدوال الشاملة في مشروع عثمانلي (Universal Function Runner)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--email", "-e", "--account", "-a", help="البريد الإلكتروني للحساب (أو معرف القلعة)")
    parser.add_argument("--func", "-f", "--function", dest="func", help="اسم الدالة المطلوب تشغيلها أو Class.method")
    parser.add_argument("--target", "-t", help="مسار الهدف بالكامل (مثل tasks.gather_2.GatherTask.run)")
    parser.add_argument("--module", "-m", "--file", dest="module", help="الموديول أو مسار الملف (اختياري مع -f)")
    parser.add_argument("--params", "-p", help="باراميترات مسماة بصيغة JSON Dictionary: '{\"tx\": 380, \"ty\": 269}'")
    parser.add_argument("--args", help="باراميترات موقعية بصيغة JSON List: '[380, 269]'")
    parser.add_argument("--kwarg", "-k", action="append", dest="kwargs", help="معامل مفتاح وقيمة: -k tx=380 -k is_stronghold=true")
    parser.add_argument("--no-connect", action="store_true", help="تعطيل الاتصال بسيرفر اللعبة حتى لو كان التوقيع يطلب conn")
    parser.add_argument("--spy", action="store_true", help="تفعيل طباعة حزم الشبكة (Spy Mode)")
    parser.add_argument("--debug", action="store_true", help="عرض سجلات تتبع الأخطاء التفصيلية (DEBUG)")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    target_query = args.target or args.func
    if not target_query:
        print("❌ خطأ: يجب تحديد الدالة المراد تشغيلها عبر --func (-f) أو --target (-t)!")
        print("مثال: python run_tool.py -e user@example.com -f check_target_busy_or_marched -k tx=380 -k ty=269")
        return 1

    try:
        # 1. اكتشاف الدالة أو الكلاس
        discovered = discover_target(target_query, file_or_mod=args.module)
        print("════════════════════════════════════════════════════════════════════")
        print(f"🎯 الهدف البرمجي : {discovered.display_name}")

        # 2. تحديد الحساب
        account = resolve_account(args.email)
        print(f"👤 الحساب المستهدف: {account.email} (UID: {account.user_id})")

        # 3. تحليل الباراميترات
        pos_args, kw_args = parse_cli_parameters(args.params, args.args, args.kwargs)
        if pos_args:
            print(f"📥 الباراميترات الموقعية (args) : {pos_args}")
        if kw_args:
            print(f"📥 الباراميترات المسماة (kwargs): {kw_args}")

        # 4. إدارة الاتصال الشبكي
        conn: Optional[GameConnection] = None
        should_connect = (not args.no_connect) and needs_network_connection(discovered)

        if should_connect:
            print("🔌 جاري الاتصال والمصادقة بسيرفر اللعبة...")
            conn = GameConnection(account)
            if args.spy:
                conn.spy_mode = True

            connected = await conn.connect()
            if not connected:
                print("❌ فشل الاتصال بسيرفر اللعبة!")
                return 1

            # ضمان اكتمال جاهزية الذاكرة الحية ووحدات التحكم الأساسية
            if hasattr(conn, "wait_for_memory_ready"):
                await conn.wait_for_memory_ready(timeout=12.0, auto_fetch_missing=True, grace_period=0.5)
            else:
                for _ in range(25):
                    await asyncio.sleep(0.15)
                    if "cityCtrl" in conn.init_data and "heroCtrl" in conn.init_data:
                        break
            print(f"✅ تم الاتصال بنجاح | المملكة: {getattr(conn, 'kingdom_id', 'غير محدد')} | UID: {conn.uid}")
        else:
            if args.no_connect:
                print("⚡ تم تخطي الاتصال الشبكي بناءً على خيار --no-connect")
            else:
                print("⚡ تشغيل محلي فوري (الدالة لا تتطلب اتصالاً شبكياً)")

        try:
            # 5. تهيئة الكائن وحقن المعاملات
            callable_to_run, final_args, final_kwargs = instantiate_and_bind(
                discovered=discovered,
                pos_args=pos_args,
                kw_args=kw_args,
                conn=conn,
                account=account,
            )

            # 6. تنفيذ الدالة
            print("⏳ جاري تنفيذ الدالة الآن...")
            start_time = time.time()

            if inspect.iscoroutinefunction(callable_to_run):
                result = await callable_to_run(*final_args, **final_kwargs)
            else:
                result = callable_to_run(*final_args, **final_kwargs)
                if inspect.iscoroutine(result):
                    result = await result

            elapsed = time.time() - start_time
            print("════════════════════════════════════════════════════════════════════")
            print(f"⏱️ اكتمل التنفيذ في {elapsed:.3f} ثانية بنجاح!")
            print("📤 النتيجة (Output / Return Value):")

            # تنسيق الناتج
            from tasks.base_task import TaskResult
            if isinstance(result, TaskResult):
                status_icon = "✅" if result.success else "⚠️"
                print(f"{status_icon} Success: {result.success}")
                print(f"💬 Message: {result.message}")
                if result.data:
                    print("📊 Data:")
                    print(json.dumps(result.data, ensure_ascii=False, indent=2, default=str))
            elif isinstance(result, (dict, list)):
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                print(repr(result))

            print("════════════════════════════════════════════════════════════════════")
            return 0

        finally:
            if conn:
                try:
                    await conn.close()
                except Exception:
                    pass

    except Exception as e:
        print(f"\n❌ خطأ أثناء التنفيذ: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        print("════════════════════════════════════════════════════════════════════")
        return 1


def main() -> None:
    try:
        code = asyncio.run(async_main())
        sys.exit(code)
    except KeyboardInterrupt:
        print("\n🛑 تم الإلغاء بواسطة المستخدم.")
        sys.exit(130)


if __name__ == "__main__":
    main()
