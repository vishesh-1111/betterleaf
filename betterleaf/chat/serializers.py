from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    messages = serializers.ListField(
        child=serializers.DictField(), allow_empty=False,
    )
    system = serializers.CharField(required=False, allow_blank=True, default="")
    resume_id = serializers.UUIDField(required=False)
