# Banky 프론트엔드 — nginx로 정적 웹(HTML/이미지) 서빙
# 모델·백엔드는 포함하지 않음. 받는 사람이 코랩 노트북으로 띄운 주소를
# 챗봇 화면의 [⚙️ 서버 설정]에 입력해서 연결한다.
FROM nginx:1.27-alpine

# 기본 nginx 설정을 SPA/정적 사이트용으로 교체
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 정적 파일 복사 (index/page2/page3/chatting + Images)
COPY index.html page2.html page3.html chatting.html /usr/share/nginx/html/
COPY Images/ /usr/share/nginx/html/Images/

EXPOSE 80
