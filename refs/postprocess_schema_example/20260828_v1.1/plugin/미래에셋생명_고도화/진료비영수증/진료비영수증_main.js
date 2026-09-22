"use strict";

const {
  Logger,
} = require("/usr/src/app/dist/apps/extn/libs/common/src/logger");

const pluginUtilCache = require.resolve("./pluginUtil_MA.js");
delete require.cache[pluginUtilCache];
const pluginUtil = require(pluginUtilCache);

const formatCache = require.resolve("./format_MA.js");
delete require.cache[formatCache];
const format = require(formatCache);

const path = require("path");
const moment = require("moment");

/**
 * plugin
 * @param {extractionResultData}
 * extractionResultData Property
 *  modelmapdata : Object // 모델 결과 map(연결정보 및 여러거자 정보 보유)
 *  allcontents : string // ocr 인식 결과를 하나의 string으로 연결한 값
 *  result : Array<Object> // schema 추출 결과값
 *  extraData : undefined | any // plugin에서 추가 정보를 최종결과에 전달 가능한 속성
 * @param {schemaObj}
 * schemaObj는 추출에 사용한 schema 객체
 * @returns
 * extractionResultData와 같은 형태로 반환해야 한다.
 */

// 날짜 정규식
const dateRegex = /(19|20)\d{2}[.\-/년월]?(0[1-9]|1[0-2]|[1-9])[.\-/일월]?(0[1-9]|[12][0-9]|3[01]|[1-9])[.일]?/g;

// 사고발생일자
let ACD_OGTDT = "";

exports.plugin = function (extractionResultData, schemaObj) {
  Logger.debug(
    `#################### ${extractionResultData?.modelmapdata?.category} Plugin START \t ${extractionResultData.modelmapdata.fileNm} ####################`
  );
  
  let values = extractionResultData?.result;
  let arrtcd = pluginUtil.getArrtcd(extractionResultData?.modelmapdata);
  let allcontents = extractionResultData?.allcontents.replace(/\s/g, ""); 

  // 추출항목 정의
  let keyObj = pluginUtil.readKeyList(
    __dirname + "/항목리스트.json",
    extractionResultData?.modelmapdata?.category
  );

  try {
    // [2026.01.13] 동적으로 항목리스트 컨트롤
    const allowedNames = new Set([
      "급여",
      "요양급여",
      "본인부담금",
      "공단부담금",
      "전액본인부담금",
      "선택진료료",
      "선택진료료이외",
      "비급여"
    ]);

    // [2026.01.13] 추출항목, 표대상항목, 표타이틀 동적으로 관리
    let relativeName = values.filter(item => 'selectRuleName' in item && allowedNames.has(item.name)).map(o => o.name);

    // 이미지 훼손으로 영역을 이상하게 잡는 경우가 있어 강제 제외
    if(relativeName.includes("본인부담금") || relativeName.includes("공단부담금") || relativeName.includes("전액본인부담금")) {
      relativeName = relativeName.filter(item => item !="급여" && item != "요양급여");
    }

    if(relativeName.includes("선택진료료") && relativeName.includes("선택진료료이외")) {
      relativeName = relativeName.filter(item => item !="비급여");
    }

    // 항목리스트 내 동적항목 추가
    keyObj["추출항목"] = [...keyObj["추출항목"], ...relativeName, ...["상한액초과금"]];
    keyObj["표대상항목"] = [...keyObj["표대상항목"], ...relativeName];
    keyObj["표타이틀"] = [...keyObj["표타이틀"], ...relativeName];

    // keyObj 기준 추출항목으로 명시된 부분만 get
    values = values.filter(item => keyObj["추출항목"].includes(item.name));
    
    // [2026.01.17] '기타' 값이 중복으로 나올 수 있어서 추가
    // let dupItms = ["행위료", "약품비", "기타"];
    let dupItms = ["기타"];


    // values: [] 
    //  -> data: [] 
    //    -> values: [] 
    //      -> .., 
    //         ..,
    //         relativeLabelsInfo: [] 
    //           -> index, 
    //              label, 
    //              coordinates: []

    let prevFlag1 = 0;
    let prevFlag2 = 0;

    values?.forEach((value, valueIdx) => {

      const name = value?.name;

      value?.data?.forEach((data) => {
        data?.values?.forEach((v, i) => {
          
          // 진료과에 해당하는 값이 '진료과/의사성명' 으로 나오는경우가 있는 케이스 대응
          if (name == "환자정보-진료과") {
            v.label = data.detectedLabel.includes("/")
              ? v.label.split("/")[0]
              : v.label;
          }

          // 상한액초과금 첫번째 값만 가져오기
          if (name == "상한액초과금" && i > 0) {
            v.label = "";
          }

          // 해당 항목의 값 오른쪽 오른쪽 컨텐츠 내용도 가져오는 경우가 있어 TCD에 해당하는 첫 번째 값만 허용
          if(name.includes("총액") || name.includes("금액")) {
            if(i != 0) v.label = "";
          }

          if (keyObj["표대상항목"]?.indexOf(name) >= 0 && v?.relativeLabelsInfo?.length > 0) {

            // 표대상항목 중 mergecell이면 첫 번째 라벨값만 반환
            if(v?.cellType == "mergecell") {

              v.relativeLabelsInfo = [v?.relativeLabelsInfo[0]];
              const labelValue = v?.ocrInfo[0];
              v.ocrInfo = [labelValue];
            }

            // 합계 중 특수기호도 일반숫자로 읽었을 경우를 대비한 방어코딩
            else if(v?.relativeLabelsInfo?.[0]?.label == "합계" && v?.ocrInfo?.length > 1) {

              // 통상 제일 왼쪽에 치우쳐진 숫자를 특수기호로 읽었다고 판단(좌표값이 매우 밀접해있어 STD에서 같이 판단했을 경우는 상정x)
              v.ocrInfo = v.ocrInfo.filter((v, i) => i != 0);
              v.label = v.ocrInfo?.[0]?.label;
            }
          }

          // 표데이터 가공
          if (
            keyObj["표대상항목"]?.indexOf(name) >= 0 &&
            v?.relativeLabelsInfo?.length > 0
          ) {

            v?.relativeLabelsInfo?.forEach((rl) => {

              if (rl?.label == "투약및조제료-행위료") {
                prevFlag1++;
              }

              if (rl?.label == "투약및조제료-약품비") {
                prevFlag2++;
              }
              
              if (rl?.label == "행위료") {
                prevFlag1++;
                if (prevFlag1 === 1) {
                  rl.label = '투약및조제료-' + rl.label;
                } else if (prevFlag1 === 2) {
                  rl.label = '주사료-' + rl.label;
                }
              } else if (rl?.label == "약품비") {
                prevFlag2++;
                if (prevFlag2 === 1) {
                  rl.label = '투약및조제료-' + rl.label;
                } else if (prevFlag2 === 2) {
                  rl.label = '주사료-' + rl.label;
                }
              }
              
              // if(rl?.label.includes("행위료") || rl?.label.includes("약품비")) {console.log(prevFlag1, prevFlag2);}
              // if(rl?.label.includes("행위료") || rl?.label.includes("약품비")) {console.log(`${rl?.label}\n`);}

              if (dupItms?.indexOf(rl?.label) >= 0) {
                // 투약및조제료: 행위료, 약품비
                // 주사료: 행위료, 약품비
                // 기타: 기본항목, 선택항목 추가
                let leftLabel = pluginUtil.setArrtcdLabel(
                  pluginUtil.getArrtcdIdxValue(
                    arrtcd,
                    pluginUtil.getArrtcdLowArr(
                      arrtcd,
                      null,
                      rl?.index,
                      "left"
                    )[0]?.index
                  )
                );

                rl.label = leftLabel + "-" + rl.label;
              } 
            });

          }

        });
      });

      // 행위료, 약품비 초기화
      prevFlag1 = 0;
      prevFlag2 = 0;

      // 발행일의 detectedLabel만 있을 경우 해당 값 추가
      if (name == "발행일" && value?.data?.length > 0) {
        if (
          value?.data[0]?.status === -3 &&
          value?.data[0]?.detectedLabel?.includes("년")
        ) {
          value.data[0].values.push({ label: value?.data[0]?.detectedLabel });
        }
      }
    });

    // console.log(JSON.stringify(values));

    // [2026.01.14] 표추출항목을 동적으로 관리
    const findRelativeLabels = values.find(v =>
      allowedNames.has(v.name) &&
      Array.isArray(v.data) &&
      Array.isArray(v.data[0]?.values) &&
      v.data[0].values.some(
        item => Array.isArray(item.relativeLabelsInfo) && item.relativeLabelsInfo.length != 0
      )
    );


    const filterRelativeLabels = values.filter(v =>
      allowedNames.has(v.name) &&
      Array.isArray(v.data) &&
      Array.isArray(v.data[0]?.values) &&
      v.data[0].values.some(
        item => Array.isArray(item.relativeLabelsInfo) && item.relativeLabelsInfo.length != 0
      )
    );

    let tableExtractItems = filterRelativeLabels.reduce((longest, v) => {
      const currentLabels = (v?.data?.[0].values ?? []).map(item => item?.relativeLabelsInfo?.[0]?.label)
                                                       .filter(label => label != null);

      return currentLabels.length > longest.length ? currentLabels : longest;
    }, []);

    // 입원료 하위항목 방어코딩
    // tableExtractItems = fixRoomArray(tableExtractItems);

    // let tableExtractItems = (findRelativeLabels?.data?.[0]?.values ?? [])
    //                           .map(item => item?.relativeLabelsInfo?.[0]?.label)
    //                           .filter(label => label != null);

    // 스키마에서 잘못 가져온 데이터 예외처리
    const removeList = ["상한액초과금", "요양기관종류"];
    tableExtractItems = tableExtractItems.filter(v => !removeList.includes(v));

    // 특정 값 push
    tableExtractItems = applyInsertRules(tableExtractItems);
    tableExtractItems = tableExtractItems.filter(item => !keyObj["표추출제외항목"].includes(item));
    tableExtractItems = [...new Set(tableExtractItems)];

    // 입원료 하위항목 제외 조건처리
    let isOneRoomKeywordYn = true;
    let isTwoRoomKeywordYn = true;
    let isFoutRoomKeywordYn = true;

    ["1인실", "2·3인실", "4인실이상"].forEach((item, idx) => {
      if(!tableExtractItems.includes(item)) {
        if(idx === 0) isOneRoomKeywordYn = false;
        if(idx === 1) isTwoRoomKeywordYn = false;
        if(idx === 2) isFoutRoomKeywordYn = false;
      }
    });
    
    if(!isOneRoomKeywordYn && !isTwoRoomKeywordYn && !isFoutRoomKeywordYn) keyObj["표추출항목"] = keyObj["표추출항목"].filter(o => o != "1인실" && o != "2·3인실" && o != "4인실이상");

    keyObj["표추출항목"] = [...keyObj["표추출항목"], ...tableExtractItems];
    
    // '소계', '합계' 둘 다 있다면 '소계'만 제외
    if (keyObj["표추출항목"].includes("소계") && keyObj["표추출항목"].includes("소계")){
      keyObj["표추출항목"] = keyObj["표추출항목"].filter(item => item !== "소계");
    }
    
    // [2026-01-17] '합계'가 없는 경우도 있어서 임의추가
    if (!keyObj["표추출항목"].includes("합계")){
      keyObj["표추출항목"].push("합계");
    }

    // 중복 제거함
    // [2026-05-13] 보정화면 끝수처리 금액을 맞추기 위한 '기타n' 행 추가
    keyObj["표추출항목"] = [...new Set(keyObj["표추출항목"]), ...["기타1", "기타2", "기타3", "기타4", "기타5"]];

    // 결과 구조 변경
    values = format.setResultFormat(
      values,
      keyObj,
      arrtcd,
      extractionResultData?.modelmapdata?.category
    );

    /**
     * 각 항목에 대한 수정 처리영역
     * 
     *  lvl_no                레벨번호
      , extc_itm_no           추출항목번호
      , extc_rst_seq          추출결과일련번호
      , hgrk_extc_itm_no      상위레벨번호
      , extc_itm_tpvl         상위항목값
      , img_extc_itnm         추출항목명
      , extc_rst_cont01       추출내용
      , extc_rst_cont08       유관관계성항목명
      , extc_rst_cont09       table 구분
      , extc_rst_img_crdn_vl  항목값좌표값
      , self_rlbtr_vl         본인신뢰도값
     */
    values.forEach((value, valueIdx) => {

      // 치과병원진료비 = 진찰료 동위선상으로 처리(format.js에서 처리하기에는 순서가 틀어지는 사유)
      if (value?.img_extc_itnm == "치과병원진료비") {
        value.img_extc_itnm = "진찰료";
      }

      // 간헐적으로 '일부~부담금'으로 키워드 잡히는 부분 '일부'를 임의삭제처리
      if (value.extc_rst_cont08?.includes("일부")) {
        value.extc_rst_cont08 = value.extc_rst_cont08.replace(/일부/g, "");
      }

      // 외래/입원
      // 체크박스 label 값 처리
      if (
        value?.img_extc_itnm?.includes("외래/입원") &&
        value?.extc_rst_cont01?.length > 0
      ) {
        if(value.extc_rst_cont01?.match(/(외래|입원)/g) != null) {
          value.extc_rst_cont01 = value.extc_rst_cont01?.match(/(외래|입원)/g)[0];
          value.extc_rst_cont01 = value.extc_rst_cont01 == "입원" ? "01" : "외래" ? "02" : ""; 
        } else {
          const titleStr = arrtcd.find(item => item.keyword === "Title")?.mergetext;
          if(titleStr?.match(/(외래|입원)/g) != null) {
            value.extc_rst_cont01 = titleStr?.match(/(외래|입원)/g)[0];
            value.extc_rst_cont01 = value.extc_rst_cont01 == "입원" ? "01" : "외래" ? "02" : ""; 
          } else {
            value.extc_rst_cont01 = "";
          }
        }
      } else if (
        value?.img_extc_itnm?.includes("외래/입원") &&
        value?.extc_rst_cont01?.length === 0
      ) {
        const titleStr = arrtcd.find(item => item.keyword === "Title")?.mergetext;
        if(!titleStr) {
          const matches = titleStr?.match(/(외래|입원)/g)[0];
          if(matches != null) value.extc_rst_cont01 = matches == "입원" ? "01" : "외래" ? "02" : "";
        }
      }

      // 환자정보-진료시작일
      if (
        value?.img_extc_itnm?.includes("환자정보-진료시작일") &&
        value?.extc_rst_cont01?.length > 0
      ) {

        const matches = value.extc_rst_cont01.match(dateRegex);

        if(matches != null) {
          if(matches.length > 1) {
            value.extc_rst_cont01 = normalizeDate(matches[0]);
          } else if(matches.length == 1) {
            value.extc_rst_cont01 = normalizeDate(matches[0]);
          }
        } else {

          if(value.extc_rst_cont01.includes("부터")) {

            const splitData = value.extc_rst_cont01.split("부터");
            if(splitData != null) {
              if(splitData.length > 1) {
                value.extc_rst_cont01 = normalizeDate(splitData[0]);
              } else if(splitData.length == 1) {
                value.extc_rst_cont01 = normalizeDate(splitData[0]);
              }
            }
            
          } else {
            const targetFormatDate = parseDateOrRange(value.extc_rst_cont01).start;
            if (!targetFormatDate) {
              value.extc_rst_cont01 = format.setDateFormat(value.extc_rst_cont01);
            } else {
              value.extc_rst_cont01 = targetFormatDate;
            }
          }
        }

        // [보험금 자동심사 컬럼 적재부] 진료비영수증: 진료시작일
        ACD_OGTDT = value.extc_rst_cont01;
      }

      // 환자정보-진료종료일
      if (
        value?.img_extc_itnm?.includes("환자정보-진료종료일") &&
        value?.extc_rst_cont01?.length > 0
      ) {

        const matches = value.extc_rst_cont01.match(dateRegex);

        if(matches != null) {
          if(matches.length > 1) {
            value.extc_rst_cont01 = normalizeDate(matches[1]);
          } else if(matches.length == 1) {
            value.extc_rst_cont01 = normalizeDate(matches[0]);
          }
        } else {

          if(value.extc_rst_cont01.includes("부터")) {

            const splitData = value.extc_rst_cont01.split("부터");
            if(splitData != null) {
              if(splitData.length > 1) {
                value.extc_rst_cont01 = normalizeDate(splitData[1]);
              } else if(splitData.length == 1) {
                value.extc_rst_cont01 = normalizeDate(splitData[0]);
              }
            }
            
          } else {
            const targetFormatDate = parseDateOrRange(value.extc_rst_cont01).end;
            if (!targetFormatDate) {
              value.extc_rst_cont01 = format.setDateFormat(value.extc_rst_cont01);
            } else {
              value.extc_rst_cont01 = targetFormatDate;
            }
          }
        }
      }

      // 환자정보-환자구분
      // [2026-02-25] 인감에 의해 STA가 합쳐져서 TCD 구분이 안되는 경우 조치
      if (value?.img_extc_itnm?.includes("환자정보-환자구분") && value?.extc_rst_cont01?.length > 0) {
        if(value.extc_rst_cont01.includes("수납일")) {
          value.extc_rst_cont01 = value.extc_rst_cont01.substring(0, value.extc_rst_cont01.indexOf("수납일"));
        }
      }

      // 의료기관정보-명칭
      // [2026-02-25] 인감에 의해 STA가 합쳐져서 TCD 구분이 안되는 경우 조치
      if (value?.img_extc_itnm?.includes("의료기관정보-명칭") && value?.extc_rst_cont01?.length > 0) {
        if(value.extc_rst_cont01.includes("전화번호")) {
          value.extc_rst_cont01 = value.extc_rst_cont01.substring(0, value.extc_rst_cont01.indexOf("전화번호"));
        }

        if(value.extc_rst_cont01.includes("대표전화")) {
          value.extc_rst_cont01 = value.extc_rst_cont01.substring(0, value.extc_rst_cont01.indexOf("대표전화"));
        }
      }

      // 발행일
      // 값이 없을 경우 전체 컨텐츠 내용에서 가져옴
      if (value?.img_extc_itnm?.includes("발행일")) {
        
        if(value?.extc_rst_cont01?.length > 0) {

          const matches = value?.extc_rst_cont01.match(dateRegex);

          if(matches != null) {
            value.extc_rst_cont01 = normalizeDate(matches[0]);
          }

        } else {
          const firstLabelValue = arrtcd.find(o => o.iskeyword && o.keyword == "합계")?.mergetext;
          const findScope = allcontents.substring(allcontents.indexOf(firstLabelValue));
          const matches = findScope.match(dateRegex);

          if(matches != null) {
            value.extc_rst_cont01 = normalizeDate(matches[0]);
            value.extrtYn = "Y";
          }
        }
      }

      // 사업자등록번호 숫자만
      if (
        value?.img_extc_itnm?.includes("사업자") &&
        value?.extc_rst_cont01?.length > 0
      ) {
        value.extc_rst_cont01 = value?.extc_rst_cont01?.replace(/[^0-9]/g, "");
      }

      //[2025-04-14] 값의 맨 앞자리가 0일 경우의 처리
      if (value?.extc_rst_cont08 !== null) {
        if (value?.extc_rst_cont01?.length > 1) {
          if (value?.extc_rst_cont01[0] === "0") {
            const zeroRegex = /^0+$/g;
            // 전부 0으로 이루어진 경우 -> 0으로 변경
            if (zeroRegex?.test(value?.extc_rst_cont01)) {
              value.extc_rst_cont01 = "0";
              // 유효 숫자 앞에 있는 0 제거
            } else {
              value.extc_rst_cont01 = value?.extc_rst_cont01?.replace(/^0+/, "");
            }
          }
        } else if (value?.extc_rst_cont01?.length === 1) {
          if (value?.extc_rst_cont01?.includes("이")) {
            value.extc_rst_cont01 = value?.extc_rst_cont01?.replace("이", "0");
          }
        }
      } else if ( ["액", "금", "료", "대", "수가"].includes(values?.img_extc_itnm) ) {
        if (value?.extc_rst_cont01?.length > 1) {
          if (value?.extc_rst_cont01[0] === "0") {
            const zeroRegex2 = /^0+$/g;
            // 전부 0으로 이루어진 경우 -> 0으로 변경
            if (zeroRegex2?.test(value?.extc_rst_cont01)) {
              value.extc_rst_cont01 = "0";

            } 
            
            // 유효 숫자 앞에 있는 0 제거
            else {
              value.extc_rst_cont01 = value?.extc_rst_cont01?.replace(/^0+/, "");
            }
          }
        } else if (value?.extc_rst_cont01?.length === 1) {
          if (value?.extc_rst_cont01?.includes("이")) {
            value.extc_rst_cont01 = value?.extc_rst_cont01?.replace("이", "0");
          }
        }
      }

      // 오데이터 방어코딩
      if (value?.img_extc_itnm == "-기타") {
        value.img_extc_itnm = "기타";
      }

      // 금액 또는 총액이 숫자가 아닌 일반 문자를 읽을 경우 상정될 수 있는 숫자로 replace 처리한다
      // 숫자와 특수문자 '-'만 허용
      if (value?.img_extc_itnm?.includes("금액") || value?.img_extc_itnm?.includes("총액")) {
        value.extc_rst_cont01 = value.extc_rst_cont01
                                .replace(/[Il\/]/g, "1")
                                .replace(/[Oo]/g, "0")
                                .replace(/B/g, "8")
                                .replace(/b/g, "6")
                                .replace(/[^0-9\-]/g, "");

        value.extc_rst_cont01 = Number(value.extc_rst_cont01).toString();
      }

      // 요양기관종류에서 간헐적으로 체크박스 영역을 v, V 문자로 간주하여 처리되는 영역을 삭제
      if (value?.img_extc_itnm?.includes("요양기관종류")) {
        value.extc_rst_cont01 = value.extc_rst_cont01.replace(/[Vv]/g, "");
      }

      // 상한액초과금
      if(value?.img_extc_itnm == "상한액초과금") {
        // [2026.01.13] 상한액초과금도 'table-contents'로 간주하여 필드값 추가
        value.extc_rst_cont08 = "본인부담금";
        value.extc_rst_cont10 = "table-contents";

        // TODO
        // [2026.03.24] 중복 객체 방어
        // if(values.filter(item => item.extc_itm_no == value.extc_itm_no).length > 1) {
        //   value.extc_itm_no = Math.max(...values.map(item => item.extc_itm_no)) + 1;
        // }
      }

      // [2026.03.24] 중복 객체 방어
      // table-contents가 잘못된 모델에서 생성될 경우 방어코딩
      // if(value?.extc_rst_cont10 == "table-contents" && valueIdx != 0) {

      //   const findTarget = values.find(item => item.img_extc_itnm == value.img_extc_itnm && item.extc_itm_tpvl == value.extc_itm_tpvl
      //                                   && item.extc_rst_cont09 == value.extc_rst_cont09);

      //   // 이전 항목명과 같은데 extc_itm_no가 상이할 경우
      //   if(value.img_extc_itnm == findTarget?.img_extc_itnm && value.extc_itm_no != findTarget?.extc_itm_no) {
      //     value.extc_itm_no = findTarget.extc_itm_no;
      //   }
      // }

    });

    // [보험금 자동심사에 필요한 컬럼 적재]
    // 진료비영수증: 진료시작일
    // YYYYMMDD 형식이 아니라면 빈 값 제공
    values?.forEach(value => {
      value.acd_ogtdt= moment(ACD_OGTDT, "YYYYMMDD", true).isValid() ? ACD_OGTDT : "";
    });

    // TODO 무결성 처리 방지를 위한 중복된 객체 제거
    // values = deduplicate(values);

    extractionResultData.result = values;

    // 로그 출력
    pluginUtil.printResultLog(values);

  } catch (error) {
    Logger.error(":: 진료비영수증 Plugin Error!! ::", JSON.stringify({
      message: error.message,
      stack: error.stack.split("\n")
    }, null, 2));
  }

  Logger.debug(
    `#################### ${extractionResultData?.modelmapdata?.category} Plugin END #################### \t ${extractionResultData.modelmapdata.fileNm}`
  );

  return extractionResultData;
};

/**
 * @name applyInsertRules
 * @description 역순으로 배열 탐색 후 RULES에 의해 splice 처리
 * @param {*} arr 
 * @returns 
 */
function applyInsertRules(arr) {

  const SPECIFIC_INSERT_RULES = {
    "1인실": {
      position: "before",
      items: ["입원료"]
    },
    "투약및조제료-행위료": {
      position: "before",
      items: ["투약및조제료"]
    },
    "주사료-행위료": {
      position: "before",
      items: ["주사료"]
    }
  };

  for (let i = arr.length - 1; i >= 0; i--) {
    const rule = SPECIFIC_INSERT_RULES[arr[i]];
    if (!rule) continue;

    const { position, items } = rule;

    if (position === "after") {
      // "입원료", "1인실", "2·3인실", "4인실이상"
      arr.splice(i + 1, 0, ...items);
    } else if (position === "before") {
      // "투약및조제료", "투약및조제료-행위료"
      arr.splice(i, 0, ...items);
    }
  }
  return arr;
}

function fixRoomArray(inputArray) {
  
  // 1. 무조건 지켜져야 할 기준 순서와 값
  const requireOrder = ["1인실", "2·3인실", "4인실이상"];

  // 2. 기존 배열에서 기준 값들만 필터링(중복 제거 포함)
  const exitstingValues = inputArray.filter(item => requireOrder.includes(item));

  // 3. 만약 기준 값들 중 하나라도 있다면 부족한 값을 찾아 채워 넣은 새로운 배열 생성
  const combined = [... new Set([...inputArray, ...requireOrder])];

  // 4. 전체 배열 중 '기준 값'들은 정해진 순서대로, 나머지 일반 값들은 뒤로 배치되도록 정렬
  return combined.sort((a, b) => {
    const indexA = requireOrder.indexOf(a);
    const indexB = requireOrder.indexOf(b);

    // 둘 다 기준 순서에 포함된 값이라면 기준 인덱스대로 정렬
    if (indexA !== -1 && indexB !== -1) return indexA - indexB;

    // a만 기준 값이라면 앞으로
    if(indexA !== -1) return -1;

    // b만 기준 값이라면 앞으로
    if(indexB !== -1) return 1;

    // 그 외 값들은 원래 순서 유지
    return 0;
  });
}

/**
 * @name parseDateOrRange
 * @description 날짜데이터 파싱
 *              단일 날짜 또는 기간 포함
 * @param {*} input 
 * @returns 
 */
function parseDateOrRange(input) {
  if (typeof input !== "string") {
    return { start: "", end: "", isRange: false };
  }

  // 날짜 1개 매칭: YYYY ([-.]|년) M ([-.]|월) [D] [일]
  const DATE_RE = String.raw`(\d{4})(?:[-.]|년)(\d{1,2})(?:[-.]|월)(\d{1,2})?(?:일)?`;

  // 1) 원본에서 " - "를 기간 구분자로 인정 (날짜 내부 '-'와 충돌 방지)
  // 2) "~"도 기간 구분자
  // 3) 공백은 무시해야 하므로 최종적으로 제거
  const normalized = input
    .replace(/\s+/g, " ")
    .replace(/\s*~\s*/g, "~")
    .replace(/\s-\s/g, "~") // " - "만 기간 구분자로 간주
    .replace(/\s+/g, "");

  // 기간(시작~종료) 먼저 시도
  const RANGE_RE = new RegExp(`^${DATE_RE}~${DATE_RE}$`);
  let m = normalized.match(RANGE_RE);
  if (m) {
    const start = normalizeDateParts(m[1], m[2], m[3]);
    const end = normalizeDateParts(m[4], m[5], m[6]);
    return { start, end, isRange: true };
  }

  // 단일 날짜 시도
  const SINGLE_RE = new RegExp(`^${DATE_RE}$`);
  m = normalized.match(SINGLE_RE);
  if (m) {
    const start = normalizeDateParts(m[1], m[2], m[3]);
    return { start, end: "", isRange: false };
  }

  // 유연 처리: 문자열 안에서 날짜 1개/2개 찾음
  const finder = new RegExp(DATE_RE, "g");
  const found = [...normalized.matchAll(finder)];

  if (found.length >= 2) {
    const start = normalizeDateParts(found[0][1], found[0][2], found[0][3]);
    const end = normalizeDateParts(found[1][1], found[1][2], found[1][3]);
    return { start, end, isRange: true };
  }
  if (found.length === 1) {
    const start = normalizeDateParts(found[0][1], found[0][2], found[0][3]);
    return { start, end: "", isRange: false };
  }

  return { start: "", end: "", isRange: false };
}

function normalizeDateParts(y, mo, d) {
  const year = String(y);
  const month = String(mo).padStart(2, "0");
  const day = d == null ? null : String(d).padStart(2, "0");

  return day ? `${year}${month}${day}` : `${year}${month}`; // day 없으면 YYYY-MM;
}

function normalizeDate(str) {
  if (!str) return null;

  // YYYYMMDD면 바로 반환
  const pureMatch = str.match(/(19|20)\d{2}(0[1-9]|1[0|2])[0-3][0-9]/);
  if (pureMatch) return pureMatch[0];

  // YYMMDD인 경우 대응
  if(str.replace(/[^0-9]/g, "").length == 6) {

    const replaceDate = str.replace(/[^0-9]/g, "");

    const yy = Number(replaceDate.slice(0, 2));
    const mm = replaceDate.slice(2, 4);
    const dd = replaceDate.slice(4, 6);

    const fullYear = (yy >= 50 ? 1900 : 2000) + yy;
    return `${fullYear}${mm}${dd}`;

  } else {

    // 한글/기호 제거 및 통일
    let cleaned = str
      .replace(/년|월/g, "-")
      .replace(/일/g, "")
      .replace(/\//g, "-")
      .replace(/\./g, "-");
  
    // YYYY-M-D → YYYYMMDD 보정
    cleaned = cleaned.replace(
      /(\d{4})-(\d{1,2})-(\d{1,2})/,
      (_, year, month, date) =>
        `${year}${month.padStart(2, "0")}${date.padStart(2, "0")}`
    );
  
    return cleaned;
  }

}

/**
 * @name deduplicate
 * @description 무결성 처리 방지를 위한 중복된 객체 제거
 * @param {*} arr 
 * @returns 
 */
function deduplicate(arr) {
  const map = new Map();

  for (const item of arr) {
    const key = `${item.extc_itm_no}_${item.extc_rst_seq}`;

    if(!map.has(key)) {
      map.set(key, []);
    }
    map.get(key).push(item);
  }

  const result = [];

  for (const group of map.values()) {

    // extc_rst_cont01의 값이 존재하는 기준
    const valid = group.filter(
      v => v.extc_rst_cont01 !== null && v.extc_rst_cont01 !== undefined && v.extc_rst_cont01 !== ""
    );

    if (valid.length > 0) {
      // 값이 있는 것 중 제일 첫 번째를 선택
      result.push(valid[0]);
    } else {
      // 전부 비어있으면 하나만 남김
      result.push(group[0]);
    }
  }

  return result;
}