from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    messages = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
    )
    system = serializers.CharField(required=False, allow_blank=True, default="")
    tools = serializers.DictField(required=False, default=dict)
    resume_id = serializers.UUIDField(required=False)
    cursor = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=0,
    )
    selection = serializers.DictField(required=False, allow_null=True, default=None)

    def validate_selection(self, value):
        if value is None:
            return value
        start = value.get("start")
        end = value.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            raise serializers.ValidationError(
                'selection must contain integer "start" and "end" keys.',
            )
        if end < start:
            raise serializers.ValidationError('selection "end" must be >= "start".')
        return value
