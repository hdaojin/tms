from django import forms


class DemoProfileForm(forms.Form):
    name = forms.CharField(label="姓名", max_length=40, required=True)
    role = forms.ChoiceField(
        label="角色",
        choices=[
            ("coach", "教练"),
            ("competitor", "选手"),
            ("expert", "专家"),
        ],
    )
    notes = forms.CharField(label="说明", widget=forms.Textarea(attrs={"rows": 4}), required=False)
    receive_notice = forms.BooleanField(label="接收通知", required=False)


class DemoUploadForm(forms.Form):
    document = forms.FileField(
        label="训练文档",
        required=True,
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx"}),
        help_text="支持 PDF、Word 文档。",
    )
    attachments = forms.FileField(
        label="补充附件",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ".zip,.7z"}),
        help_text="可选上传压缩包。",
    )
