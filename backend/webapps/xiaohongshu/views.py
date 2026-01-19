"""
Xiaohongshu sentiment monitoring REST API views
"""
import logging
from datetime import datetime, timedelta

from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import TruncHour
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from llm.check_utils.utils import check_token_and_get_llm
from .models import MonitorKeyword, XiaohongshuNote, NoteAnalysisResult
from .serializers import (
    MonitorKeywordSerializer,
    XiaohongshuNoteSerializer,
    NoteUploadSerializer,
    BatchNoteUploadSerializer,
    NoteListFilterSerializer,
    AnalysisReviewSerializer,
)
from .services.keyword_matcher import match_keywords

logger = logging.getLogger('django')


# ============== Keyword Management APIs ==============

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def keywords_list_create(request):
    """
    GET: List keywords with pagination
    POST: Create a new keyword
    """
    if request.method == 'GET':
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            is_active = request.query_params.get('is_active')
            category = request.query_params.get('category')

            queryset = MonitorKeyword.objects.all()
            if is_active is not None:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')
            if category:
                queryset = queryset.filter(category=category)

            paginator = Paginator(queryset, page_size)
            keywords = paginator.get_page(page)

            serializer = MonitorKeywordSerializer(keywords, many=True)
            return Response({
                'status': 'success',
                'data': {
                    'items': serializer.data,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_pages': paginator.num_pages,
                        'total_count': paginator.count,
                    }
                },
                'message': '获取关键词列表成功',
                'code': 200
            })
        except Exception as e:
            logger.error(f'获取关键词列表失败: {e}')
            return Response({
                'status': 'error',
                'data': None,
                'message': f'获取关键词列表失败: {str(e)}',
                'code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'POST':
        try:
            serializer = MonitorKeywordSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(created_by=request.user)
                return Response({
                    'status': 'success',
                    'data': serializer.data,
                    'message': '创建关键词成功',
                    'code': 201
                }, status=status.HTTP_201_CREATED)
            return Response({
                'status': 'error',
                'data': None,
                'message': '创建关键词失败',
                'errors': serializer.errors,
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'创建关键词失败: {e}')
            return Response({
                'status': 'error',
                'data': None,
                'message': f'创建关键词失败: {str(e)}',
                'code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def keyword_detail(request, pk):
    """
    GET: Get keyword detail
    PUT: Update keyword
    DELETE: Delete keyword
    """
    try:
        keyword = MonitorKeyword.objects.get(pk=pk)
    except MonitorKeyword.DoesNotExist:
        return Response({
            'status': 'error',
            'data': None,
            'message': '关键词不存在',
            'code': 404
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = MonitorKeywordSerializer(keyword)
        return Response({
            'status': 'success',
            'data': serializer.data,
            'message': '获取关键词详情成功',
            'code': 200
        })

    elif request.method == 'PUT':
        try:
            serializer = MonitorKeywordSerializer(keyword, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'status': 'success',
                    'data': serializer.data,
                    'message': '更新关键词成功',
                    'code': 200
                })
            return Response({
                'status': 'error',
                'data': None,
                'message': '更新关键词失败',
                'errors': serializer.errors,
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'更新关键词失败: {e}')
            return Response({
                'status': 'error',
                'data': None,
                'message': f'更新关键词失败: {str(e)}',
                'code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'DELETE':
        try:
            keyword.delete()
            return Response({
                'status': 'success',
                'data': None,
                'message': '删除关键词成功',
                'code': 200
            })
        except Exception as e:
            logger.error(f'删除关键词失败: {e}')
            return Response({
                'status': 'error',
                'data': None,
                'message': f'删除关键词失败: {str(e)}',
                'code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============== Note Data APIs ==============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notes_list(request):
    """
    GET: List notes with pagination and filters
    """
    try:
        filter_serializer = NoteListFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response({
                'status': 'error',
                'data': None,
                'message': '参数错误',
                'errors': filter_serializer.errors,
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        params = filter_serializer.validated_data
        page = params.get('page', 1)
        page_size = params.get('page_size', 20)

        queryset = XiaohongshuNote.objects.all()

        # Apply filters
        if params.get('status'):
            queryset = queryset.filter(status=params['status'])
        if params.get('note_type'):
            queryset = queryset.filter(note_type=params['note_type'])
        if params.get('keyword'):
            queryset = queryset.filter(description__icontains=params['keyword'])
        if params.get('start_date'):
            queryset = queryset.filter(extracted_at__date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(extracted_at__date__lte=params['end_date'])

        queryset = queryset.order_by('-extracted_at')

        paginator = Paginator(queryset, page_size)
        notes = paginator.get_page(page)

        serializer = XiaohongshuNoteSerializer(notes, many=True)
        return Response({
            'status': 'success',
            'data': {
                'items': serializer.data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                }
            },
            'message': '获取笔记列表成功',
            'code': 200
        })
    except Exception as e:
        logger.error(f'获取笔记列表失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'获取笔记列表失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def upload_note(request):
    """
    POST: Upload a single note from crawler client
    Uses ExternalService Token authentication
    """
    # Authenticate using ExternalService Token
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    check_result, llm_model_dict, user_id, service_target, service_appid = \
        check_token_and_get_llm(request.META.get('REMOTE_ADDR'), auth_header)

    if "error" in check_result:
        return Response(check_result, status=status.HTTP_401_UNAUTHORIZED)

    try:
        serializer = NoteUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'data': None,
                'message': '数据格式错误',
                'errors': serializer.errors,
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        note_id = data['note_id']

        # Parse extracted_at
        extracted_at = None
        if data.get('extracted_at'):
            try:
                extracted_at = datetime.strptime(data['extracted_at'], '%Y-%m-%d:%H-%M-%S')
            except ValueError:
                pass

        # Create or update note
        note, created = XiaohongshuNote.objects.update_or_create(
            note_id=note_id,
            defaults={
                'author_name': data.get('author', ''),
                'author_avatar': data.get('author_avatar', ''),
                'description': data.get('description', ''),
                'note_type': data.get('type', 'image'),
                'images': data.get('images', []),
                'tags': data.get('tags', []),
                'likes_count': data.get('likes', 0),
                'collects_count': data.get('collects', 0),
                'comments_count': data.get('comments', 0),
                'publish_time': data.get('publish_time', ''),
                'location': data.get('location', ''),
                'top_comments': data.get('top_comments', []),
                'extracted_at': extracted_at,
                'card_index': data.get('card_index', 0),
                'source': service_target or '',
                'raw_data': request.data,
            }
        )

        # Match keywords
        matched = match_keywords(note)

        return Response({
            'status': 'success',
            'data': {
                'note_id': note_id,
                'created': created,
                'matched_keywords': matched,
            },
            'message': '上传笔记成功',
            'code': 201 if created else 200
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    except Exception as e:
        logger.error(f'上传笔记失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'上传笔记失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def upload_notes_batch(request):
    """
    POST: Batch upload notes from crawler client
    Uses ExternalService Token authentication
    """
    # Authenticate using ExternalService Token
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    check_result, llm_model_dict, user_id, service_target, service_appid = \
        check_token_and_get_llm(request.META.get('REMOTE_ADDR'), auth_header)

    if "error" in check_result:
        return Response(check_result, status=status.HTTP_401_UNAUTHORIZED)

    try:
        serializer = BatchNoteUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'data': None,
                'message': '数据格式错误',
                'errors': serializer.errors,
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        notes_data = data['notes']
        source = data.get('source', service_target or '')

        created_count = 0
        updated_count = 0
        failed_count = 0
        results = []

        for note_data in notes_data:
            try:
                note_id = note_data['note_id']

                # Parse extracted_at
                extracted_at = None
                if note_data.get('extracted_at'):
                    try:
                        extracted_at = datetime.strptime(note_data['extracted_at'], '%Y-%m-%d:%H-%M-%S')
                    except ValueError:
                        pass

                note, created = XiaohongshuNote.objects.update_or_create(
                    note_id=note_id,
                    defaults={
                        'author_name': note_data.get('author', ''),
                        'author_avatar': note_data.get('author_avatar', ''),
                        'description': note_data.get('description', ''),
                        'note_type': note_data.get('type', 'image'),
                        'images': note_data.get('images', []),
                        'tags': note_data.get('tags', []),
                        'likes_count': note_data.get('likes', 0),
                        'collects_count': note_data.get('collects', 0),
                        'comments_count': note_data.get('comments', 0),
                        'publish_time': note_data.get('publish_time', ''),
                        'location': note_data.get('location', ''),
                        'top_comments': note_data.get('top_comments', []),
                        'extracted_at': extracted_at,
                        'card_index': note_data.get('card_index', 0),
                        'source': source,
                        'raw_data': note_data,
                    }
                )

                # Match keywords
                matched = match_keywords(note)

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                results.append({
                    'note_id': note_id,
                    'status': 'created' if created else 'updated',
                    'matched_keywords': matched,
                })

            except Exception as e:
                failed_count += 1
                results.append({
                    'note_id': note_data.get('note_id', 'unknown'),
                    'status': 'failed',
                    'error': str(e),
                })

        return Response({
            'status': 'success',
            'data': {
                'created_count': created_count,
                'updated_count': updated_count,
                'failed_count': failed_count,
                'results': results,
            },
            'message': f'批量上传完成: 创建{created_count}条, 更新{updated_count}条, 失败{failed_count}条',
            'code': 200
        })

    except Exception as e:
        logger.error(f'批量上传笔记失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'批量上传笔记失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def note_detail(request, note_id):
    """
    GET: Get note detail
    DELETE: Delete note
    """
    try:
        note = XiaohongshuNote.objects.get(note_id=note_id)
    except XiaohongshuNote.DoesNotExist:
        return Response({
            'status': 'error',
            'data': None,
            'message': '笔记不存在',
            'code': 404
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = XiaohongshuNoteSerializer(note)
        return Response({
            'status': 'success',
            'data': serializer.data,
            'message': '获取笔记详情成功',
            'code': 200
        })

    elif request.method == 'DELETE':
        try:
            note.delete()
            return Response({
                'status': 'success',
                'data': None,
                'message': '删除笔记成功',
                'code': 200
            })
        except Exception as e:
            logger.error(f'删除笔记失败: {e}')
            return Response({
                'status': 'error',
                'data': None,
                'message': f'删除笔记失败: {str(e)}',
                'code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============== Analysis APIs ==============

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def analysis_review(request, note_id):
    """
    PUT: Update analysis result with manual review
    """
    try:
        note = XiaohongshuNote.objects.get(note_id=note_id)
    except XiaohongshuNote.DoesNotExist:
        return Response({
            'status': 'error',
            'data': None,
            'message': '笔记不存在',
            'code': 404
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        analysis_result = note.analysis_result
    except NoteAnalysisResult.DoesNotExist:
        return Response({
            'status': 'error',
            'data': None,
            'message': '分析结果不存在',
            'code': 404
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        serializer = AnalysisReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'data': None,
                'message': '参数错误',
                'errors': serializer.errors,
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        if data.get('manual_category'):
            analysis_result.manual_category = data['manual_category']
        if data.get('review_notes'):
            analysis_result.review_notes = data['review_notes']

        analysis_result.is_reviewed = True
        analysis_result.reviewed_by = request.user
        analysis_result.reviewed_at = timezone.now()
        analysis_result.save()

        return Response({
            'status': 'success',
            'data': {
                'note_id': note_id,
                'is_reviewed': True,
                'manual_category': analysis_result.manual_category,
                'final_category': analysis_result.final_category,
            },
            'message': '人工复核成功',
            'code': 200
        })

    except Exception as e:
        logger.error(f'人工复核失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'人工复核失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============== Statistics APIs ==============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stats_overview(request):
    """
    GET: Get overall statistics
    """
    try:
        total_notes = XiaohongshuNote.objects.count()
        pending_notes = XiaohongshuNote.objects.filter(status='pending').count()
        completed_notes = XiaohongshuNote.objects.filter(status='completed').count()
        failed_notes = XiaohongshuNote.objects.filter(status='failed').count()

        # Category distribution
        category_stats = NoteAnalysisResult.objects.values('category').annotate(
            count=Count('id')
        ).order_by('category')

        # Keyword stats
        total_keywords = MonitorKeyword.objects.count()
        active_keywords = MonitorKeyword.objects.filter(is_active=True).count()

        return Response({
            'status': 'success',
            'data': {
                'notes': {
                    'total': total_notes,
                    'pending': pending_notes,
                    'completed': completed_notes,
                    'failed': failed_notes,
                },
                'categories': list(category_stats),
                'keywords': {
                    'total': total_keywords,
                    'active': active_keywords,
                }
            },
            'message': '获取统计概览成功',
            'code': 200
        })

    except Exception as e:
        logger.error(f'获取统计概览失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'获取统计概览失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stats_hourly(request):
    """
    GET: Get 24-hour trend statistics
    """
    try:
        local_tz = timezone.get_current_timezone()
        now = timezone.localtime(timezone.now(), local_tz)
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        start_time = current_hour - timedelta(hours=23)

        hourly_counts = (
            XiaohongshuNote.objects
            .filter(extracted_at__gte=start_time)
            .annotate(hour=TruncHour('extracted_at', tzinfo=local_tz))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )

        stats_dict = {}
        for item in hourly_counts:
            hour_local = timezone.localtime(item['hour'], local_tz)
            stats_dict[hour_local.replace(tzinfo=None)] = item['count']

        hourly_data = []
        for i in range(24):
            hour_start = start_time + timedelta(hours=i)
            hour_key = hour_start.replace(tzinfo=None)
            count = stats_dict.get(hour_key, 0)
            hourly_data.append({
                'hour': hour_start.isoformat(),
                'label': hour_start.strftime('%H:00'),
                'count': count
            })

        return Response({
            'status': 'success',
            'data': {
                'hourly_stats': hourly_data,
                'total_24h': sum(item['count'] for item in hourly_data)
            },
            'message': '获取24小时趋势成功',
            'code': 200
        })

    except Exception as e:
        logger.error(f'获取24小时趋势失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'获取24小时趋势失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
