from __future__ import annotations

from rest_framework import generics, status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import Document
from .serializers import DocumentDetailSerializer, DocumentSerializer, ParseDocumentResponseSerializer, UploadDocumentSerializer
from .services import parse_pdf_to_text


class DocumentListCreateView(generics.ListCreateAPIView):
    queryset = Document.objects.all().order_by("-uploaded_at")
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.request.method.upper() == "POST":
            return UploadDocumentSerializer
        return DocumentSerializer

    def create(self, request, *args, **kwargs):
        serializer = UploadDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        f = serializer.validated_data["file"]
        doc = Document.objects.create(file=f, original_name=f.name)
        out = DocumentSerializer(instance=doc, context={"request": request})
        return Response(out.data, status=status.HTTP_200_OK)


class DocumentDetailView(generics.RetrieveAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentDetailSerializer


class DocumentParseView(GenericAPIView):
    serializer_class = ParseDocumentResponseSerializer

    @extend_schema(request=None, responses=ParseDocumentResponseSerializer)
    def post(self, request, pk):
        doc = generics.get_object_or_404(Document, pk=pk)
        result = parse_pdf_to_text(doc)
        return Response({"document_id": str(doc.id), "pages": result.pages, "chunks": result.chunks})

