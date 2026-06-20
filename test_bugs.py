import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gunpowder_archive.settings')
django.setup()

from formulas.models import Formula
from django.core.exceptions import ValidationError

print("=== 测试1: 没有文献的配方提交评审 ===")
f = Formula.objects.filter(literature__isnull=True).first()
if f:
    print(f"  测试配方: {f.formula_no}, literature={f.literature}")
    old_status = f.review_status
    f.review_status = 'pending'
    try:
        f.full_clean()
        print("  ❌ 错误: 验证通过了，本应失败")
    except ValidationError as e:
        print(f"  ✅ 正确: 验证失败 - {e.message_dict}")
    f.review_status = old_status
else:
    print("  ℹ️  没有找到无文献的配方，跳过测试")

print("\n=== 测试2: 高风险但无安全说明的配方 ===")
f = Formula.objects.filter(safety_level='high').first()
if f:
    print(f"  测试配方: {f.formula_no}, safety_level={f.safety_level}, safety_note='{f.safety_note}'")
    old_status = f.review_status
    old_note = f.safety_note
    f.safety_note = ''
    f.review_status = 'pending'
    try:
        f.full_clean()
        print("  ❌ 错误: 验证通过了，本应失败")
    except ValidationError as e:
        print(f"  ✅ 正确: 验证失败 - {e.message_dict}")
    f.review_status = old_status
    f.safety_note = old_note
else:
    print("  ℹ️  没有找到高风险配方，跳过测试")

print("\n=== 测试3: 年代筛选 ===")
qs = Formula.objects.filter(era__icontains='宋代')
print(f"  搜索关键词: '宋代'")
print(f"  找到 {qs.count()} 条配方")
for f in qs:
    print(f"    - {f.formula_no}: era='{f.era}'")
if qs.count() > 0:
    print("  ✅ 正确: 年代筛选正常工作")
