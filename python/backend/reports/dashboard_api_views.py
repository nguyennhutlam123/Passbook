from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdmin
from .dashboard import (
    DASHBOARD_SECTIONS,
    analytics_dashboard,
    get_dashboard_metrics,
)


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response(get_dashboard_metrics())


class AdminDashboardSectionView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, section):
        if section == 'analytics':
            result = analytics_dashboard(request.query_params)
            if 'error' in result:
                return Response({'detail': result['error']}, status=400)
            return Response(result)

        dashboard = DASHBOARD_SECTIONS.get(section)
        if dashboard is None:
            return Response({'detail': 'Dashboard section not found.'}, status=404)
        return Response(dashboard())
