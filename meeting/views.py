from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from django.http import FileResponse

from pathlib import Path

from .forms import MeetingUploadForm
from .models import Meeting


@login_required
def upload_meeting(request):
    # 检查用户是否属于"班务"组
    if not request.user.groups.filter(name='班务').exists():
        messages.error(request, '只有班务人员才能上传会议记录文件！')
        return redirect('meeting:meeting_list')
    
    if request.method == 'POST':
        form = MeetingUploadForm(request.POST, request.FILES)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.uploaded_by = request.user

            # 获取上传的文件
            uploaded_file = request.FILES['upload']
            
            # 构建新的文件名：日期-文件标题.pdf
            date_str = meeting.date.strftime('%Y.%m.%d')
            new_filename = f"{date_str}-{meeting.title}.pdf"
            
            # 设置数据库中的文件名字段
            meeting.filename = new_filename
            
            # 将文件内容读取到内存
            file_content = uploaded_file.read()
            
            # 保存上传文件（使用新文件名）
            meeting.upload.save(new_filename, ContentFile(file_content), save=False)
            
            # 保存模型实例
            meeting.save()
            messages.success(request, '会议记录文件上传成功!')
            return redirect('meeting:meeting_list')
    else:
        form = MeetingUploadForm()
    
    return render(request, 'meeting/upload_meeting.html', {
        'form': form, 
        'title': '上传会议记录'
    })


@login_required
def meeting_list(request):
    meetings = Meeting.objects.all().order_by('-date')
    
    # 检查用户是否是班务人员
    is_class_admin = request.user.groups.filter(name='班务').exists()
    
    context = {
        'title': '会议记录列表',
        'meetings': meetings,
        'is_class_admin': is_class_admin,
    }
    
    return render(request, 'meeting/meeting_list.html', context)


@login_required
def meeting_detail(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    if not meeting.upload or not meeting.upload.path:
        messages.error(request, '会议记录文件不存在或未上传。')
        return redirect('meeting:meeting_list')
    
    file_path = Path(meeting.upload.path)
    if not file_path.exists():
        messages.error(request, '会议记录文件不存在或已被删除。')
        return redirect('meeting:meeting_list')
    
    try:
        response = FileResponse(
            open(file_path, 'rb'), 
            content_type='application/pdf'
        )
        # 使用 inline 让浏览器直接显示PDF内容而不是下载
        response['Content-Disposition'] = f'inline; filename="{meeting.filename}"'
        return response
    except Exception as e:
        messages.error(request, f'下载文件时发生错误: {str(e)}')
        return redirect('meeting:meeting_list')
    