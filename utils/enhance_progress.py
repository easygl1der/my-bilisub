#!/usr/bin/env python3
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 读取原文件
with open('process_csv_workflow.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到并替换主循环中的进度显示部分
new_lines = []
skip_until = None

for i, line in enumerate(lines):
    # 跳过旧代码
    if skip_until:
        if skip_until in line:
            skip_until = None
        continue

    # 替换主循环的进度显示
    if "for i, video in enumerate(videos, 1):" in line:
        # 找到循环开始，替换整个循环
        new_lines.append(line)
        new_lines.append('        # 显示进度\n')
        new_lines.append('        progress_pct = (i / len(videos)) * 100\n')
        new_lines.append('        print(f"\\n\\n")\n')
        new_lines.append('        print(f"{"#" * 80}")\n')
        new_lines.append('        print(f"# {"🎬" * 20}")\n')
        new_lines.append('        print(f"{"#" * 80}")\n')
        new_lines.append('        print(f"# 进度: [{i}/{len(videos)}] {progress_pct:.1f}%")\n')
        new_lines.append('        print(f"# 当前: {video["title"]}")\n')
        new_lines.append('        print(f"{"#" * 80}")\n')
        new_lines.append('        print(f"# 剩余: {len(videos) - i} 个视频")\n')
        new_lines.append('        print(f"{"#" * 80}\\n")\n')
        # 跳过旧的打印语句直到结果处理
        skip_until = 'result = process_single_video'
        new_lines.append('        result = process_single_video(\n')
        continue

    # 替换处理单个视频的打印
    if 'print(f"\\n\'=\'*80}")' in line and '处理视频' in lines[i+1]:
        skip_until = 'start_time = time.time()'
        continue

    if 'print(f"\\n\'#\'*80}")' in line and '进度:' in lines[i+1]:
        skip_until = 'result = process_single_video'
        continue

    # 替换等待提示
    if 'if i < len(videos):' in line and '等待3秒' in lines[i+3]:
        new_lines.append(line)
        new_lines.append('        # 显示等待提示和预计完成时间\n')
        new_lines.append('        avg_time = sum(r["total_time"] for r in results) / len(results) if results else 45\n')
        new_lines.append('        remaining_time = avg_time * (len(videos) - i)\n')
        new_lines.append('        print(f"\\n{"⏳" * 30}")\n')
        new_lines.append('        print(f"⏳ 等待3秒后处理下一个...")\n')
        new_lines.append('        print(f"⏳ 预计剩余时间: {remaining_time/60:.1f} 分钟")\n')
        new_lines.append('        print(f"{"⏳" * 30}\\n")\n')
        skip_until = 'time.sleep(3)'
        new_lines.append('        time.sleep(3)\n')
        continue

    new_lines.append(line)

# 写回文件
with open('process_csv_workflow.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Done! Progress display has been enhanced.")
print("Now showing:")
print("  - Progress percentage")
print("  - Current video title")
print("  - Remaining count")
print("  - Estimated time remaining")
